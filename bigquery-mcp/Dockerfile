# BigQuery MCP server for Google Cloud Run..
#
# Runs Google's MCP Toolbox for Databases (pinned to the same version as the
# local toolbox.exe) over Streamable HTTP, serving the BigQuery sources, tools
# and toolsets defined in tools.yaml.
#
# Build (context = this folder):
#   docker build -t bigquery-mcp ./bigquery-mcp
#
# Authentication on Cloud Run uses the service's runtime service account
# (Application Default Credentials) -- no key file is baked into the image.

FROM debian:12-slim

ARG TOOLBOX_VERSION=1.6.0

# rca-certificates is required for TLS to the BigQuery / Google APIs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL "https://storage.googleapis.com/mcp-toolbox-for-databases/v${TOOLBOX_VERSION}/linux/amd64/toolbox" \
        -o /usr/local/bin/toolbox \
    && chmod +x /usr/local/bin/toolbox \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY tools.yaml /app/tools.yaml

# Cloud Run injects PORT (defaults to 8080). Toolbox must bind 0.0.0.0:$PORT.
ENV PORT=8080

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080

# tools.yaml reads BIGQUERY_PROJECT (and optional BIGQUERY_* vars) from the
# environment at runtime -- set them as Cloud Run env vars / secrets.
CMD ["/bin/sh", "-c", "exec toolbox --config /app/tools.yaml --address 0.0.0.0 --port ${PORT}"]
