"""FastAPI application factory wiring the model runtime, agent suite, and session registry.

Startup and shutdown use the lifespan context manager; the runtime is injectable so tests can run offline.
All routes live under /api; when a built frontend directory exists it is served at the root, so one container ships both.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from insidegame.adapters.model_client import ModelRuntime, build_model_runtime
from insidegame.adapters.telemetry import setup_telemetry
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

FRONTEND_ORIGINS: list[str] = os.getenv("FRONTEND_ORIGINS", "http://localhost:5199").split(",")
STATIC_DIR: str = os.getenv("STATIC_DIR", "")
API_PREFIX: str = "/api"
API_TITLE: str = "Inside the Game API"
API_VERSION: str = "0.1.0"
ERROR_STATUS: dict[type[Exception], int] = {
    FixtureError: 400, PersonaConfigError: 400, SessionNotFoundError: 404, SessionLimitError: 429,
}


ErrorHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def create_app(
    runtime: ModelRuntime | None = None, sleep: Sleeper = asyncio.sleep, static_dir: str = STATIC_DIR
) -> FastAPI:
    """Build the application.

    Defaults: runtime is the environment model runtime, sleep is asyncio.sleep, static_dir is STATIC_DIR.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runtime is None:
            setup_telemetry()
        resolved = runtime or build_model_runtime()
        app.state.runtime = resolved
        app.state.registry = SessionRegistry(create_agent_suite(resolved.client), resolved.policy, sleep)
        yield
        await app.state.registry.shutdown()

    app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    for error, status in ERROR_STATUS.items():
        app.add_exception_handler(error, _handler(status))
    app.include_router(routes_meta.router, prefix=API_PREFIX)
    app.include_router(routes_matches.router, prefix=API_PREFIX)
    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


def _handler(status: int) -> ErrorHandler:
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})
    return handle
