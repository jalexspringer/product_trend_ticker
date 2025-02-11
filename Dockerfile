FROM python:3.12-slim

LABEL maintainer="alex.springer@impact.com" \
      version="1.0.0" \
      description="Trending Product Categories Microsite"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src src/

# Install dependencies using uv
RUN uv pip install -e .

# Expose port (Heroku will override this)
ENV PORT=8000
EXPOSE $PORT

# Use Heroku's PORT environment variable
CMD gunicorn src.app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - --log-level info --timeout 120