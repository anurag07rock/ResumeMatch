# ==============================================================================
# ResumeMatch Backend Dockerfile
# Production-grade, reproducible container for FastAPI + sentence-transformers (CPU)
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PORT=8000

WORKDIR /app

# Install curl for reliable health checks and clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies reproducibly with CPU-only wheels for PyTorch
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /app/requirements.txt

# Create dedicated non-root user for execution security
RUN useradd --create-home --home-dir /home/appuser --shell /bin/bash --uid 1000 appuser

# Copy application configuration and codebase
COPY alembic.ini /app/alembic.ini
COPY data/skills_taxonomy.json /app/data/skills_taxonomy.json
COPY backend/alembic /app/backend/alembic
COPY backend/app /app/backend/app
COPY scripts /app/scripts

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check verifies FastAPI liveness via /health
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command starts Uvicorn production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
