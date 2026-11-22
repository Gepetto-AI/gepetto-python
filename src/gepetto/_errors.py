from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._job import Job


class GepettoError(Exception):
    """Every error of the SDK. ``code`` is stable, for your code (``unknown_room``, ``test_limit_reached``...);
    the message says what to do next, for a person.

    .. code-block:: python

        try:
            job = gepetto.furnish(url=photo_url, room_id="bedroom", style_id="modrn")
        except GepettoError as e:
            e.code     # "unknown_style"
            e.param    # "styleId"
            e.status   # 400
            str(e)     # No style "modrn". The list is on GET /v2/styles.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        param: str | None = None,
        job_id: str | None = None,
        job: Job | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        """The API's error code, such as ``invalid_parameter``, or ``timeout`` and ``connection_error`` from the SDK."""
        self.message = message
        self.status = status
        """The HTTP status, None when the API was not reached."""
        self.param = param
        """The parameter the error is about, such as ``roomId``."""
        self.job_id = job_id
        """The job concerned, when a render was started: follow it with get_job()."""
        self.job = job
        """The failed or unfinished job, when there is one."""

    def __repr__(self) -> str:
        return f"GepettoError(code={self.code!r}, status={self.status!r}, message={self.message!r})"


class TransportError(Exception):
    """The API could not be reached, or did not answer in time. Raised by a transport."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out
