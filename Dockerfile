# Multi-stage Dockerfile for Local Subtitle Alignment Workbench API
# Meets containerization requirements for AITU Master's NIR-4 milestone.

FROM python:3.12-slim-bookworm AS base

# Install system audio dependencies (ffmpeg, libsndfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install build dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy project metadata and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install package with speech and API optional dependencies
RUN pip install --no-cache-dir .[api]

# Create non-root runtime user for container security
RUN useradd -u 1000 -m workbench && \
    chown -R workbench:workbench /app
USER workbench

# Expose HTTP REST port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch production ASGI server
CMD ["uvicorn", "subtitle_workbench.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
