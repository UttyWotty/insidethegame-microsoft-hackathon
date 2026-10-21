"""Identification of API callers for per-client rate limits.

Behind the Container Apps ingress the client address is the last X-Forwarded-For entry, the one the platform proxy
appended; earlier entries are client-supplied and could be forged. Without the header the socket peer is used.
"""

from fastapi import Request

FORWARDED_FOR_HEADER: str = "x-forwarded-for"
UNKNOWN_CLIENT: str = "unknown"


def client_key(request: Request) -> str:
    """The caller's address for rate limiting, or UNKNOWN_CLIENT when neither header nor peer is available."""
    forwarded = request.headers.get(FORWARDED_FOR_HEADER, "")
    if forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else UNKNOWN_CLIENT
