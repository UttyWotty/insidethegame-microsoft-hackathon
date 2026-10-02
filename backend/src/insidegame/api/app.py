"""FastAPI application factory wiring the model runtime, agent suite, and session registry.

Startup and shutdown use the lifespan context manager; the runtime is injectable so tests can run offline.
Domain exceptions are mapped to HTTP status codes in one place.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from insidegame.adapters.model_client import ModelRuntime, build_model_runtime
from insidegame.agents.factory import create_agent_suite
from insidegame.api import routes_matches, routes_meta
from insidegame.core.exceptions import (
    FixtureError,
    PersonaConfigError,
    SessionLimitError,
    SessionNotFoundError,
)
from insidegame.live.registry import SessionRegistry
from insidegame.live.session import Sleeper

FRONTEND_ORIGINS: list[str] = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
API_TITLE: str = "Inside the Game API"
API_VERSION: str = "0.1.0"
ERROR_STATUS: dict[type[Exception], int] = {
    FixtureError: 400, PersonaConfigError: 400, SessionNotFoundError: 404, SessionLimitError: 429,
}


ErrorHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def create_app(runtime: ModelRuntime | None = None, sleep: Sleeper = asyncio.sleep) -> FastAPI:
    """Build the application; runtime defaults to the environment model runtime and sleep to asyncio.sleep."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = runtime or build_model_runtime()
        app.state.runtime = resolved
        app.state.registry = SessionRegistry(create_agent_suite(resolved.client), resolved.policy, sleep)
        yield
        await app.state.registry.shutdown()

    app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    for error, status in ERROR_STATUS.items():
        app.add_exception_handler(error, _handler(status))
    app.include_router(routes_meta.router)
    app.include_router(routes_matches.router)
    return app


def _handler(status: int) -> ErrorHandler:
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})
    return handle
