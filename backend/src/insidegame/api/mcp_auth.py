"""Optional bearer-token guard for the MCP endpoint.

MCP tools can start matches and spend model tokens, so deployments can require a shared key.
When no key is configured the endpoint is open, which suits local development.
"""

import hmac

from starlette.types import ASGIApp, Receive, Scope, Send

UNAUTHORIZED_BODY: bytes = b'{"error": "unauthorized"}'
HTTP_UNAUTHORIZED: int = 401
BEARER_PREFIX: str = "Bearer "


class BearerTokenGuard:
    """ASGI middleware rejecting HTTP requests without the expected bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.token:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"").decode()
            expected = f"{BEARER_PREFIX}{self.token}"
            if not hmac.compare_digest(supplied, expected):
                await send({"type": "http.response.start", "status": HTTP_UNAUTHORIZED,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": UNAUTHORIZED_BODY})
                return
        await self.app(scope, receive, send)
