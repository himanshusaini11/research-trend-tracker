# Stage 1: builder — install dependencies into a virtualenv
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install runtime deps only (no dev extras) into .venv
RUN uv sync --frozen --no-dev

# Stage 2: runtime — minimal image with only what's needed to run
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN useradd --system --no-create-home appuser

# Copy the virtualenv built in stage 1
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY app/ ./app/

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
