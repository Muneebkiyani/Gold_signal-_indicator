# Production Dockerfile for XAUUSD Gold Signal System
# Optimized for Hugging Face Spaces (UID 1000, Port 7860) & Cloud Containers
FROM python:3.10-slim

# Install system dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces requires non-root user UID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Copy dependencies first for Docker caching
COPY --chown=user:user gold-signal-system/backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY --chown=user:user gold-signal-system/backend/ $HOME/app/

# Ensure SQLite data directory exists with write permissions
RUN mkdir -p $HOME/app/data

# Hugging Face default port is 7860 (overridable via $PORT)
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
