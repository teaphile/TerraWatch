# ==============================================================
# TerraWatch — Unified Dockerfile for Hugging Face Spaces
# Builds frontend + serves everything from one container
# ==============================================================

# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim

# HF Spaces requires a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/app/ app/

# Copy built frontend into expected location
COPY --from=frontend-build /build/dist /app/frontend/dist

# Create writable data directory
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

# HF Spaces expects port 7860
EXPOSE 7860

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=7860
ENV DATABASE_URL=sqlite+aiosqlite:///./data/terrawatch.db
ENV CORS_ORIGINS=*
ENV LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
