# RAG Knowledge Base - Production Dockerfile

ARG BUILD_ENV=production
FROM python:3.11-slim

# Build metadata
LABEL maintainer="RAG KB Team"
LABEL description="RAG Knowledge Base API and Worker"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Create non-root user
RUN groupadd -r ragkb && useradd -r -g ragkb ragkb

# Copy and install Python dependencies first (for layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "." \
    && pip install --no-cache-dir gunicorn uvicorn[standard]

# Copy application code
COPY . .

# Create storage directory and set permissions
RUN mkdir -p /data/storage /tmp/ragkb \
    && chown -R ragkb:ragkb /data/storage /tmp/ragkb

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV STORAGE_PATH=/data/storage

# Switch to non-root user
USER ragkb

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "50", "app.backend.main:app"]
