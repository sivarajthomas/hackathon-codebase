# Production image for the Invoice Processing SaaS backend (FastAPI).
#
# Build from the repository root (so the context matches cloudbuild.yaml):
#   docker build -f backend/Dockerfile -t invoice-backend .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The FastAPI package lives at /app/app (module path: app.main:app).
COPY backend/app ./app

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Cloud Run injects $PORT; bind uvicorn to it. Shell form allows expansion.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
