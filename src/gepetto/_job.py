from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

JobStatus = Literal["pending", "processing", "success", "error"]


@dataclass(frozen=True)
class JobError:
    code: str
    message: str


@dataclass(frozen=True)
class Job:
    """A render. A tool of the client returns it once the image is ready: ``output`` is then its public URL."""

    id: str
    status: str
    """``pending``, ``processing``, ``success`` or ``error``."""
    tool: str
    """``declutter``, ``furnish``, ``sunshine``, ``creative-redesign``, ``surfaces``, ``enhance``, ``upscale``,
    ``camera-move`` or ``transition``."""
    mode: str | None
    """declutter and furnish: ``auto`` or ``zone``; sunshine: the sky id; surfaces: ``walls``, ``floor`` or ``finish``;
    enhance: ``straighten`` or None; upscale: ``2k`` or ``4k``; creative-redesign: None."""
    output: str | None
    """The image (an MP4 video for camera-move and transition), once ``status`` is ``success``. A public URL: copy
    it to your storage if you keep it."""
    error: JobError | None
    price_cents: int
    """Price in euro cents (0 with a test key; charged only on success)."""
    test: bool
    created_at: str | None
    finished_at: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Job:
        """A job as the API sends it."""
        error = data.get("error")
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "")),
            tool=str(data.get("tool", "")),
            mode=data.get("mode"),
            output=data.get("output"),
            error=JobError(str(error.get("code", "")), str(error.get("message", ""))) if isinstance(error, dict) else None,
            price_cents=int(data.get("priceCents") or 0),
            test=bool(data.get("test", False)),
            created_at=data.get("createdAt"),
            finished_at=data.get("finishedAt"),
        )

    @property
    def is_finished(self) -> bool:
        """Done, one way or the other: ``success`` or ``error``."""
        return self.status in ("success", "error")

    @property
    def is_success(self) -> bool:
        return self.status == "success" and self.output is not None
