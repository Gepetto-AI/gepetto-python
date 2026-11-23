"""The official Python SDK of the Gepetto API v2: real estate photo editing.

.. code-block:: python

    from gepetto import Gepetto

    gepetto = Gepetto()  # reads GEPETTO_API_KEY
    job = gepetto.furnish(url=photo_url, room_id="living_room", style_id="scandinave")
    print(job.output)
"""

from ._client import DEFAULT_BASE_URL, CameraMove, Gepetto, mask_from_file
from ._errors import GepettoError, TransportError
from ._job import Job, JobError, JobStatus
from ._transport import Transport, urllib_transport
from ._version import __version__
from ._webhook import verify_webhook

__all__ = [
    "DEFAULT_BASE_URL",
    "CameraMove",
    "Gepetto",
    "GepettoError",
    "Job",
    "JobError",
    "JobStatus",
    "Transport",
    "TransportError",
    "__version__",
    "mask_from_file",
    "urllib_transport",
    "verify_webhook",
]
