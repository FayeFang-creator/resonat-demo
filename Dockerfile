# Single-image deploy: build the frontend, then serve it and the backend from one
# origin via serve.py. Targets Hugging Face Spaces (Docker SDK, port 7860); any
# container host works too.
#
#   docker build -t sounds-like-you .
#   docker run -p 7860:7860 sounds-like-you
#
# No API key required: Cyanite is retired, search runs against the local catalog in
# this repository, and audio is served to the browser by Jamendo's public CDN.

# ---------- 1. Build the frontend ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. Runtime ----------
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# HF Spaces runs containers as non-root; uv needs a writable cache directory
RUN useradd -m -u 1000 app
USER app
ENV HOME=/home/app \
    PATH=/home/app/.local/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/home/app/.venv \
    PYTHONUNBUFFERED=1
WORKDIR /home/app/src

# Cache the dependency layer: reinstall only when pyproject/uv.lock changes
COPY --chown=app:app backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --frozen --no-dev

COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app serve.py ./
COPY --from=frontend --chown=app:app /build/dist ./frontend/dist

EXPOSE 7860
CMD ["uv", "run", "--project", "backend", "--no-sync", \
     "uvicorn", "serve:root", "--host", "0.0.0.0", "--port", "7860"]
