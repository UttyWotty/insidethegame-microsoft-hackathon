"""Process entry point that serves the API with uvicorn.

Host, port, and the graceful shutdown limit (which stops open SSE streams from blocking shutdown) come from the
environment with explicit defaults.
Run with: python -m insidegame.main
"""

import os

import uvicorn

from insidegame.api.app import create_app

API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
SHUTDOWN_GRACE_S: int = int(os.getenv("SHUTDOWN_GRACE_S", "5"))

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT, timeout_graceful_shutdown=SHUTDOWN_GRACE_S)
