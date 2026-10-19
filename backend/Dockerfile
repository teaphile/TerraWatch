FROM python:3.11-slim

# Non-root runtime user (matches the Hugging Face Spaces image).
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System dependencies: curl is used by the container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies first, so code changes do not invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code and ML artefacts (trained models are optional).
COPY app/ app/
COPY ml/ ml/
RUN mkdir -p data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite+aiosqlite:///./data/terrawatch.db

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
