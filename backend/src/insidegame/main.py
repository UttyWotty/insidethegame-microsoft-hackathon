"""Process entry point that serves the API with uvicorn.

Host and port come from environment variables with explicit defaults.
Run with: python -m insidegame.main
"""

import os

import uvicorn

from insidegame.api.app import create_app

API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
