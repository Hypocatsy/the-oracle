# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + serve built frontend
FROM python:3.12-slim AS production
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create data directory (Railway volume will mount over this)
RUN mkdir -p /app/data/chroma /app/data/uploads

# Put the venv on PATH so we don't need `uv run`
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8050

WORKDIR /app/backend
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8050}
