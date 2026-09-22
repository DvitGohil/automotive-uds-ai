# ── Backend Dockerfile ──────────────────────────────────────────────
# Multi-stage build for smaller production image
# Build context: project root (../)
# ────────────────────────────────────────────────────────────────────

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time deps (gcc needed for some wheels)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /build/requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

LABEL maintainer="Automotive UDS AI Team"
LABEL description="FastAPI backend for Automotive UDS Diagnostics Assistant"

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (context is project root)
COPY backend/ /app/backend/
COPY requirements.txt /app/requirements.txt

# Create data directories (volumes will be mounted here)
RUN mkdir -p /app/data/vector_store /app/data/documents /app/data/uploads && \
    chown -R appuser:appuser /app

USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run the application
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
