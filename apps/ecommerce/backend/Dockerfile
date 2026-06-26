FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen from lock file)
RUN uv sync --frozen

# Copy application code
COPY backend/ backend/
COPY scripts/ scripts/

EXPOSE 8001
