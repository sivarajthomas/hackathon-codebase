# Production-ready image for the Invoice/Shipment MCP server.
#
# Build from the repository root (mcp-platform/):
#   docker build -f gcs-mcp/Dockerfile -t gcs-mcp .

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    PORT=8080

WORKDIR /app

COPY gcs-mcp/requirements.txt ./requirements.txt
COPY shared/requirements.txt ./shared-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r shared-requirements.txt

COPY shared ./shared
COPY gcs-mcp ./gcs-mcp

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH="/app:/app/gcs-mcp"

WORKDIR /app/gcs-mcp
EXPOSE 8080

CMD ["python", "app.py"]
