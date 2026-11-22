from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Mapping, Protocol

from ._errors import TransportError


class Transport(Protocol):
    """Sends one HTTP request. Pass your own to ``Gepetto(transport=...)`` for tests or another HTTP library.

    Returns the HTTP status and the body. Raises TransportError when the API could not be reached in time.
    """

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, bytes]: ...


def urllib_transport(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> tuple[int, bytes]:
    """The default transport: the standard library, nothing to install."""
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        # An error status is an answer of the API, not a transport failure
        return error.code, error.read()
    except (socket.timeout, TimeoutError) as error:
        raise TransportError("timed out", timed_out=True) from error
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, (socket.timeout, TimeoutError))
        raise TransportError(str(error.reason), timed_out=timed_out) from error
    except OSError as error:
        raise TransportError(str(error)) from error
