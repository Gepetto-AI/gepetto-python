from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

from ._errors import GepettoError
from ._job import Job


def verify_webhook(
    body: bytes | str,
    signature: str | None,
    secret: str | None = None,
    *,
    tolerance: int = 300,
) -> Job:
    """Checks the ``Gepetto-Signature`` header of a webhook and returns its job.

    :param body: The raw body of the request, before any JSON decoding.
    :param signature: The ``Gepetto-Signature`` header.
    :param secret: Your webhook secret (``webhook_secret`` of ``account()``, or ``npx @gepetto/cli secret``);
        by default GEPETTO_WEBHOOK_SECRET. Test and live keys have different secrets.
    :param tolerance: Seconds: an older signature is refused.
    :raises GepettoError: ``invalid_signature`` when the webhook does not come from Gepetto.
    """
    secret = secret or os.environ.get("GEPETTO_WEBHOOK_SECRET")
    if not secret:
        raise GepettoError(
            "invalid_parameter",
            "No webhook secret: pass it to verify_webhook(), or set GEPETTO_WEBHOOK_SECRET. "
            "It is webhook_secret in gepetto.account(), or `npx @gepetto/cli secret`.",
        )
    if not signature:
        raise _invalid("no Gepetto-Signature header")

    # The header is "t=<unix time>,v1=<hex>"
    parts = dict(part.strip().split("=", 1) for part in signature.split(",") if "=" in part)
    timestamp, given = parts.get("t", ""), parts.get("v1", "")
    if not timestamp.isdigit() or not given:
        raise _invalid("malformed header")
    if abs(time.time() - int(timestamp)) > tolerance:
        raise _invalid("timestamp too old")

    raw = body.encode() if isinstance(body, str) else body
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, given):
        raise _invalid("signature mismatch (wrong secret, or the body was modified)")

    try:
        data = json.loads(raw)
    except ValueError:
        raise _invalid("the body is not JSON") from None
    if not isinstance(data, dict):
        raise _invalid("the body is not a job")
    return Job.from_dict(data)


def _invalid(why: str) -> GepettoError:
    return GepettoError("invalid_signature", f"Invalid webhook signature: {why}.")
