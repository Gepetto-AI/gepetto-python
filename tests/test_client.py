"""The client with a fake transport: each test says what the API answers, and checks what was sent."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest

from gepetto import Gepetto, GepettoError, Job, TransportError, mask_from_file, verify_webhook


class FakeApi:
    """Answers the given responses in order, and keeps the requests."""

    def __init__(self, *answers: tuple[int, Any] | TransportError) -> None:
        self.answers = list(answers)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> tuple[int, bytes]:
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": json.loads(body) if body else None})
        answer = self.answers.pop(0)
        if isinstance(answer, TransportError):
            raise answer
        status, data = answer
        return status, json.dumps(data).encode()


def job(status: str, output: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "id": "job_1", "status": status, "tool": "furnish", "mode": "auto", "output": output, "error": None,
        "priceCents": 0, "test": True, "createdAt": "2026-11-22T10:00:00Z", "finishedAt": None, **extra,
    }


def client(api: FakeApi) -> Gepetto:
    return Gepetto("test_key", transport=api, timeout=30)


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gepetto._client._backoff", lambda attempt: None)
    monkeypatch.setattr("gepetto._client.POLL_INTERVAL", 0.01)


def test_a_tool_sends_the_api_names_and_returns_the_finished_job() -> None:
    api = FakeApi((200, job("success", "https://img/output.jpg")))

    result = client(api).furnish(url="https://img/photo.jpg", room_id="living_room", style_id="scandinave")

    assert result.output == "https://img/output.jpg"
    assert result.is_success
    request = api.requests[0]
    assert request["method"] == "POST"
    assert request["url"].endswith("/v2/furnish")
    assert request["body"] == {"url": "https://img/photo.jpg", "roomId": "living_room", "styleId": "scandinave"}
    assert request["headers"]["Authorization"] == "Bearer test_key"
    assert request["headers"]["Idempotency-Key"]


def test_unset_options_are_not_sent() -> None:
    api = FakeApi((200, job("success", "https://img/o.jpg")))

    client(api).declutter(url="https://img/p.jpg", keep_fireplace=True)

    assert api.requests[0]["body"] == {"url": "https://img/p.jpg", "keepFireplace": True}


def test_a_running_job_is_followed_until_its_image_is_ready() -> None:
    api = FakeApi((200, job("processing")), (200, job("success", "https://img/o.jpg")))

    result = client(api).enhance(url="https://img/p.jpg")

    assert result.output == "https://img/o.jpg"
    assert api.requests[1]["method"] == "GET"
    assert api.requests[1]["url"].endswith("/v2/job/job_1")


def test_a_webhook_returns_the_pending_job_at_once() -> None:
    api = FakeApi((202, job("pending")))

    result = client(api).sunshine(url="https://img/p.jpg", sky_id="sunny", webhook="https://me/hook")

    assert result.status == "pending"
    assert len(api.requests) == 1


def test_a_503_is_retried_with_the_same_idempotency_key() -> None:
    api = FakeApi(
        (503, {"status": "error", "code": "internal_error", "message": "Try again."}),
        (200, job("success", "https://img/o.jpg")),
    )

    client(api).upscale(url="https://img/p.jpg", resolution="4k", idempotency_key="photo-42:upscale")

    assert [r["headers"]["Idempotency-Key"] for r in api.requests] == ["photo-42:upscale", "photo-42:upscale"]


def test_a_dropped_connection_is_retried_with_the_same_key() -> None:
    api = FakeApi(TransportError("Connection reset by peer"), (200, job("success", "https://img/o.jpg")))

    result = client(api).enhance(url="https://img/p.jpg")

    assert result.output == "https://img/o.jpg"
    assert api.requests[0]["headers"]["Idempotency-Key"] == api.requests[1]["headers"]["Idempotency-Key"]


def test_an_api_error_raises_with_its_code_and_param() -> None:
    api = FakeApi((400, {"status": "error", "code": "unknown_style", "message": 'No style "modrn".', "param": "styleId"}))

    with pytest.raises(GepettoError) as caught:
        client(api).furnish(url="https://img/p.jpg", room_id="bedroom", style_id="modrn")

    assert caught.value.code == "unknown_style"
    assert caught.value.param == "styleId"
    assert caught.value.status == 400
    assert str(caught.value) == 'No style "modrn".'
    assert len(api.requests) == 1, "a 400 is not retried"


def test_a_failed_render_raises_with_the_job() -> None:
    api = FakeApi((200, job("error", error={"code": "render_failed", "message": "The render failed."})))

    with pytest.raises(GepettoError) as caught:
        client(api).furnish(url="https://img/p.jpg", room_id="bedroom", style_id="modern")

    assert caught.value.code == "render_failed"
    assert caught.value.job_id == "job_1"
    assert isinstance(caught.value.job, Job)


def test_without_a_key_the_message_says_how_to_get_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEPETTO_API_KEY", raising=False)

    with pytest.raises(GepettoError) as caught:
        Gepetto()

    assert caught.value.code == "missing_api_key"
    assert "npx @gepetto/cli" in str(caught.value)


def test_the_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEPETTO_API_KEY", "test_from_env")

    assert Gepetto().is_test


def test_list_jobs_returns_jobs() -> None:
    api = FakeApi((200, [job("success", "https://img/o.jpg")]))

    jobs = client(api).list_jobs(status="success", limit=5)

    assert isinstance(jobs[0], Job)
    assert api.requests[0]["url"].endswith("/v2/jobs?status=success&limit=5")


def test_mask_from_file_gives_a_data_url(tmp_path: Any) -> None:
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"\x89PNG\r\n\x1a\nrest")

    assert mask_from_file(mask).startswith("data:image/png;base64,")


def signed(body: str, secret: str, at: int | None = None) -> str:
    timestamp = str(at if at is not None else int(time.time()))
    digest = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_a_webhook_is_verified() -> None:
    body = json.dumps(job("success", "https://img/o.jpg"))

    assert verify_webhook(body, signed(body, "whsec_test"), "whsec_test").output == "https://img/o.jpg"


def test_a_webhook_with_a_wrong_signature_is_refused() -> None:
    body = json.dumps(job("success", "https://img/o.jpg"))

    with pytest.raises(GepettoError, match="signature mismatch"):
        verify_webhook(body, signed(body, "another_secret"), "whsec_test")


def test_an_old_webhook_is_refused() -> None:
    with pytest.raises(GepettoError, match="timestamp too old"):
        verify_webhook("{}", signed("{}", "whsec_test", at=int(time.time()) - 3600), "whsec_test")


def test_a_video_is_followed_until_the_mp4_is_ready() -> None:
    api = FakeApi(
        (202, job("processing", tool="camera-move", mode="zoom_in")),
        (200, job("success", "https://img/output.mp4", tool="camera-move", mode="zoom_in")),
    )

    result = client(api).camera_move(url="https://img/p.jpg", camera="zoom_in")

    assert result.output == "https://img/output.mp4"
    assert api.requests[0]["url"].endswith("/v2/video/camera-move")
    assert api.requests[0]["body"] == {"url": "https://img/p.jpg", "camera": "zoom_in"}


def test_a_transition_from_a_job_sends_the_api_names() -> None:
    api = FakeApi((202, job("processing", tool="transition", mode="custom")))

    client(api).transition(job_id="job_9", prompt="The furniture appears", webhook="https://me/hook")

    assert api.requests[0]["url"].endswith("/v2/video/transition")
    assert api.requests[0]["body"] == {"jobId": "job_9", "prompt": "The furniture appears", "webhook": "https://me/hook"}
