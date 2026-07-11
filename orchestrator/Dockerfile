# Production image for the MCP Orchestrator backend.
#
# Build from the repository root (mcp-platform/) so the Dockerfile can COPY the
# reused ./shared package (structured logging), matching invoice-mcp:
#   docker build -f orchestrator/Dockerfile -t orchestrator .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    PORT=8080

WORKDIR /app

COPY orchestrator/requirements.txt ./requirements.txt
COPY shared/requirements.txt ./shared-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r shared-requirements.txt

COPY shared ./shared
COPY orchestrator ./orchestrator

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH="/app:/app/orchestrator"

WORKDIR /app/orchestrator
EXPOSE 8080

CMD ["python", "app.py"]
