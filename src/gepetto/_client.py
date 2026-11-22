from __future__ import annotations

import base64
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlencode

from ._errors import GepettoError, TransportError
from ._job import Job, JobStatus
from ._transport import Transport, urllib_transport
from ._version import __version__

DEFAULT_BASE_URL = "https://europe-west1-gepettoai.cloudfunctions.net/v2"
# Seconds. A render is stopped by the API after 450 s: 10 minutes covers it, retries included.
DEFAULT_TIMEOUT = 600.0
DEFAULT_MAX_RETRIES = 2
# Seconds between two checks of a running job
POLL_INTERVAL = 2.5


class Gepetto:
    """The client of the Gepetto API v2: real estate photo editing.

    .. code-block:: python

        from gepetto import Gepetto

        gepetto = Gepetto()  # reads GEPETTO_API_KEY

        job = gepetto.furnish(
            url="https://example.com/empty-living-room.jpg",
            room_id="living_room",
            style_id="scandinave",
        )
        print(job.output)  # the URL of the image

    Each tool waits for the image and returns the finished Job, or raises a GepettoError.
    With ``webhook=...``, it returns at once with the pending job instead.

    The parameters are those of the API, in snake_case: ``room_id`` is ``roomId`` in the docs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: Transport | None = None,
    ) -> None:
        """
        :param api_key: Your API key. By default GEPETTO_API_KEY.
        :param timeout: Seconds a call waits for its image, retries included (each call can set its own).
        :param max_retries: Retries after a network error, a 429 or a 5xx.
        :param transport: Your own HTTP layer (see ``gepetto.Transport``), for tests or another library.
        """
        key = (api_key or os.environ.get("GEPETTO_API_KEY") or "").strip()
        if not key:
            raise GepettoError(
                "missing_api_key",
                "No API key: pass it to Gepetto(...) or set GEPETTO_API_KEY. "
                "Get a free test key with `npx @gepetto/cli login` then `npx @gepetto/cli init`.",
            )
        self._api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._transport: Transport = transport or urllib_transport

    @property
    def is_test(self) -> bool:
        """A test key (``test_...``): free renders, 200 per account."""
        return self._api_key.startswith("test_")

    # --- Tools ----------------------------------------------------------------------------------------------------
    # Every tool also takes, optionally:
    #   idempotency_key="photo-42:furnish"  one key per photo and per tool: a retry never renders, nor bills, twice
    #   timeout=120                          seconds, for this call
    # The url of the photo is a public http(s) URL: upload the photo to your own storage first.

    def declutter(
        self,
        *,
        url: str,
        mask: str | None = None,
        keep_kitchen: bool | None = None,
        keep_bathroom: bool | None = None,
        keep_fireplace: bool | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """Without a mask, the whole room is emptied; with a mask, only what is painted in white is removed."""
        return self._render(
            "/declutter",
            {
                "url": url,
                "mask": mask,
                "keepKitchen": keep_kitchen,
                "keepBathroom": keep_bathroom,
                "keepFireplace": keep_fireplace,
                "webhook": webhook,
            },
            idempotency_key,
            timeout,
        )

    def furnish(
        self,
        *,
        url: str,
        room_id: str | None = None,
        style_id: str | None = None,
        mask: str | None = None,
        furniture_id: str | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """Without a mask, the whole room is furnished (room_id and style_id). With a mask, the painted zone is
        furnished as a room (room_id and style_id), or with one piece of furniture (furniture_id, style_id optional)."""
        return self._render(
            "/furnish",
            {
                "url": url,
                "roomId": room_id,
                "styleId": style_id,
                "mask": mask,
                "furnitureId": furniture_id,
                "webhook": webhook,
            },
            idempotency_key,
            timeout,
        )

    def sunshine(
        self,
        *,
        url: str,
        sky_id: str,
        light_projection: bool | None = None,
        pool_light: bool | None = None,
        add_leafs: bool | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """A blue sky and the matching light, outside or through the windows."""
        return self._render(
            "/sunshine",
            {
                "url": url,
                "skyId": sky_id,
                "lightProjection": light_projection,
                "poolLight": pool_light,
                "addLeafs": add_leafs,
                "webhook": webhook,
            },
            idempotency_key,
            timeout,
        )

    def creative_redesign(
        self,
        *,
        url: str,
        room_id: str,
        style_id: str,
        preserve_floor: bool | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """The room redesigned in a style: furniture, materials and colours change, the architecture stays."""
        return self._render(
            "/creative-redesign",
            {
                "url": url,
                "roomId": room_id,
                "styleId": style_id,
                "preserveFloor": preserve_floor,
                "webhook": webhook,
            },
            idempotency_key,
            timeout,
        )

    def surfaces(
        self,
        *,
        url: str,
        surface: Literal["walls", "floor", "finish"],
        wall_type: str | None = None,
        custom_wall_color: str | None = None,
        preserve_ceiling: bool | None = None,
        floor_type: str | None = None,
        include_baseboard: bool | None = None,
        finish_id: str | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """One surface per call: "walls" (wall_type, or "custom" with custom_wall_color), "floor" (floor_type)
        or "finish" (finish_id)."""
        return self._render(
            "/surfaces",
            {
                "url": url,
                "surface": surface,
                "wallType": wall_type,
                "customWallColor": custom_wall_color,
                "preserveCeiling": preserve_ceiling,
                "floorType": floor_type,
                "includeBaseboard": include_baseboard,
                "finishId": finish_id,
                "webhook": webhook,
            },
            idempotency_key,
            timeout,
        )

    def enhance(
        self,
        *,
        url: str,
        straighten: bool | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """Light and colours corrected, nothing redrawn, at the size of the photo. straighten: converging verticals."""
        return self._render(
            "/enhance", {"url": url, "straighten": straighten, "webhook": webhook}, idempotency_key, timeout
        )

    def upscale(
        self,
        *,
        url: str,
        resolution: Literal["2k", "4k"] | None = None,
        webhook: str | None = None,
        idempotency_key: str | None = None,
        timeout: float | None = None,
    ) -> Job:
        """Enlarged to about 4 megapixels ("2k") or 16 megapixels ("4k", the default)."""
        return self._render(
            "/upscale", {"url": url, "resolution": resolution, "webhook": webhook}, idempotency_key, timeout
        )

    # --- Jobs -----------------------------------------------------------------------------------------------------

    def get_job(self, job_id: str) -> Job:
        """A job, finished or not."""
        return Job.from_dict(self._get(f"/job/{quote(job_id, safe='')}"))

    def wait_for_job(self, job_id: str, *, timeout: float | None = None) -> Job:
        """Waits for a job started with a webhook, or after a timeout. Returns it once its image is ready."""
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        return _finished(self._poll(job_id, deadline))

    def list_jobs(self, *, status: JobStatus | None = None, limit: int | None = None) -> list[Job]:
        """The latest jobs of the key, newest first."""
        query = urlencode({k: v for k, v in {"status": status, "limit": limit}.items() if v is not None})
        jobs = self._get("/jobs" + (f"?{query}" if query else ""))
        return [Job.from_dict(job) for job in jobs]

    # --- Lists: the valid ids of the parameters -------------------------------------------------------------------

    def list_rooms(self) -> list[dict[str, Any]]:
        """room_id, with the modes of each room ("auto": whole room, "zone": with a mask)."""
        return self._get("/rooms")  # type: ignore[no-any-return]

    def list_styles(self) -> list[dict[str, Any]]:
        """style_id."""
        return self._get("/styles")  # type: ignore[no-any-return]

    def list_furnitures(self) -> dict[str, list[dict[str, Any]]]:
        """furniture_id, grouped by type."""
        return self._get("/furnitures")  # type: ignore[no-any-return]

    def list_skies(self) -> list[dict[str, Any]]:
        """sky_id."""
        return self._get("/skies")  # type: ignore[no-any-return]

    def list_surfaces(self) -> dict[str, list[dict[str, Any]]]:
        """wall_type, floor_type and finish_id: {"walls": [...], "floors": [...], "finishes": [...]}."""
        return self._get("/surfaces")  # type: ignore[no-any-return]

    # --- Account --------------------------------------------------------------------------------------------------

    def account(self) -> dict[str, Any]:
        """The key type, the test renders used, the webhook secret..."""
        return self._get("/account")  # type: ignore[no-any-return]

    def usage(self) -> dict[str, Any]:
        """The consumption of the current billing period."""
        return self._get("/usage")  # type: ignore[no-any-return]

    # --- Internals ------------------------------------------------------------------------------------------------

    def _render(
        self, path: str, params: dict[str, Any], idempotency_key: str | None, timeout: float | None
    ) -> Job:
        body = {name: value for name, value in params.items() if value is not None}
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)

        # The same key on every attempt: a retry answers the job already created, never a second render (nor a
        # second charge). It also covers a connection dropped while the render runs: the retry gets the running
        # job, which is then followed with GET /job/{id}.
        key = idempotency_key or str(uuid.uuid4())

        status, data = self._send("POST", path, body, key, deadline, retry_connection=True)
        job = Job.from_dict(_json(status, data))
        if "webhook" in body:
            return job
        if not job.is_finished:
            job = self._poll(job.id, deadline)
        return _finished(job)

    def _get(self, path: str) -> Any:
        status, data = self._send("GET", path, None, None, time.monotonic() + self.timeout)
        return _json(status, data)

    def _poll(self, job_id: str, deadline: float) -> Job:
        while True:
            status, data = self._send("GET", f"/job/{quote(job_id, safe='')}", None, None, deadline)
            job = Job.from_dict(_json(status, data))
            if job.is_finished:
                return job
            if time.monotonic() + POLL_INTERVAL >= deadline:
                raise GepettoError(
                    "timeout",
                    f"Job {job_id} is still {job.status}: stopped waiting (timeout). It goes on: "
                    f"follow it with get_job('{job_id}') or wait_for_job('{job_id}').",
                    job_id=job_id,
                    job=job,
                )
            time.sleep(POLL_INTERVAL)

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        idempotency_key: str | None,
        deadline: float,
        *,
        retry_connection: bool = False,
    ) -> tuple[int, Any]:
        """Sends a request, with retries after a network error, a 429 or a 5xx (a POST only with an idempotency key)."""
        retryable = method == "GET" or idempotency_key is not None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": f"gepetto-python/{__version__}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        payload = None if body is None else json.dumps(body).encode()

        attempt = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _timeout_error()
            try:
                status, raw = self._transport(method, self.base_url + path, headers, payload, remaining)
            except TransportError as error:
                if error.timed_out:
                    raise _timeout_error() from error
                max_attempts = max(self.max_retries, 2) if retry_connection else self.max_retries
                if retryable and attempt < max_attempts and time.monotonic() < deadline:
                    _backoff(attempt)
                    attempt += 1
                    continue
                hint = (
                    f" Retry with the same idempotency_key ({idempotency_key}): a render already started is not run twice."
                    if idempotency_key
                    else ""
                )
                raise GepettoError("connection_error", f"Could not reach the Gepetto API ({error}).{hint}") from error

            try:
                data = json.loads(raw) if raw else None
            except ValueError:
                data = _NOT_JSON

            # 502 is a render that failed: it is answered, not retried
            transient = status == 429 or (status >= 500 and status != 502)
            if transient and retryable and attempt < self.max_retries and time.monotonic() < deadline:
                _backoff(attempt)
                attempt += 1
                continue
            return status, data


# --- Helpers --------------------------------------------------------------------------------------------------------


def mask_from_file(path: str | os.PathLike[str]) -> str:
    """A local image as a base64 data URL, to send as a ``mask`` without hosting it (PNG, JPEG or WebP, 5 MB at most).
    A mask is a black image with the zone painted in white, at the proportions of the photo."""
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise GepettoError("invalid_parameter", f"Could not read the mask file {path}.") from error
    if data.startswith(b"\x89PNG"):
        kind = "image/png"
    elif data.startswith(b"\xff\xd8"):
        kind = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = "image/webp"
    else:
        raise GepettoError("invalid_parameter", f"The mask {path} must be a PNG, JPEG or WebP image.")
    return f"data:{kind};base64," + base64.b64encode(data).decode()


_NOT_JSON = object()


def _json(status: int, data: Any) -> Any:
    """The body of a successful answer; else the error the API sent."""
    if 200 <= status < 300:
        if data is _NOT_JSON or data is None:
            raise GepettoError("invalid_response", "The API answered something that is not JSON.", status=status)
        return data
    error = data if isinstance(data, dict) else {}
    raise GepettoError(
        str(error.get("code") or ("rate_limited" if status == 429 else "invalid_response")),
        str(error.get("message") or f"The API answered HTTP {status}."),
        status=status,
        param=error.get("param"),
        # A render that failed during a synchronous call (502) carries its job id
        job_id=error.get("id"),
    )


def _finished(job: Job) -> Job:
    """The job, if its image is ready; else its error. A failed render is never charged."""
    if job.is_success:
        return job
    raise GepettoError(
        job.error.code if job.error else "render_failed",
        job.error.message if job.error else "The render failed. You were not charged. Try again.",
        job_id=job.id,
        job=job,
    )


def _backoff(attempt: int) -> None:
    """Waits 1 s, 2 s, 4 s... (8 s at most), with a little jitter."""
    time.sleep(min(8, 2**attempt) * (0.8 + random.random() * 0.4))


def _timeout_error() -> GepettoError:
    return GepettoError(
        "timeout",
        "The call took longer than its timeout. A render already started goes on: find it with list_jobs().",
    )
