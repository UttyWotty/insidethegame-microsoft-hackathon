# Multi-stage image that builds the React frontend and runs the FastAPI backend serving both.
# The final stage runs as a non-root user and defaults to the Foundry model provider with managed identity.
# Built and deployed by azd (see azure.yaml) or locally with: docker build -t inside-the-game .

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/app/static \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    MODEL_PROVIDER=foundry
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 appuser
COPY --from=frontend /frontend/dist ./static
USER appuser
EXPOSE 8000
CMD ["python", "-m", "insidegame.main"]
