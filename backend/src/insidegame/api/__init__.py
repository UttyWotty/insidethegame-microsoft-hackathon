"""HTTP API layer exposing match sessions, metadata, and live server-sent event streams.

Routers stay thin: they validate input, call the live registry, and map domain errors to HTTP status codes.
The application is assembled in app.py using the FastAPI lifespan pattern.
"""
