# Enterprise MCP Platform

A reusable platform hosting two **independent** MCP (Model Context Protocol)
servers, each representing a **business capability** rather than a storage
technology. Servers are built to deploy independently to Google Cloud Run using
the FastMCP **Streamable HTTP** transport.

## Servers

| Server          | Capability                     | Backend                       |
|-----------------|--------------------------------|-------------------------------|
| `bigquery-mcp`  | BigQuery data access & catalog | BigQuery (MCP Toolbox binary) |
| `invoice-mcp`   | Invoice & shipment information | Google Cloud Storage          |

> The backend technology is **never** exposed. Only business-oriented tools are
> published.

## Layered architecture

```
Tool Layer  ->  Service Layer  ->  Repository Layer  ->  Connector Layer  ->  External System
```

- **Tool layer** — registers MCP tools, validates input, formats responses. No business logic.
- **Service layer** — business logic, transformation, aggregation, orchestration. No SDK calls.
- **Repository layer** — data-access abstraction; chooses a connector; hides the backend.
- **Connector layer** — the only layer that talks to external systems.

## Shared package

`shared/` provides reusable building blocks imported by every server:
`auth`, `config`, `connectors` (base classes), `exceptions`, `logging`,
`models` (common + response envelopes) and `utils` (helpers + FastMCP bootstrap).

## Running a server locally

```powershell
# Invoice MCP (Python) -- from the repository root (mcp-platform/)
$env:PYTHONPATH = "$PWD;$PWD\invoice-mcp"
$env:APP_ENV = "development"
pip install -r invoice-mcp/requirements.txt -r shared/requirements.txt
python invoice-mcp/app.py

# BigQuery MCP (Google MCP Toolbox binary)
. .\scripts\Load-EnvFile.ps1 .env
.\bigquery-mcp\toolbox.exe --config .\bigquery-mcp\tools.yaml --stdio
```

## Running tests

```powershell
pip install pytest pydantic
# From a server directory, e.g.:
cd invoice-mcp; python -m pytest
```

## Building a Docker image

Images are built from the **repository root** so the `shared` package is
included:

```powershell
docker build -f invoice-mcp/Dockerfile -t invoice-mcp .
```

## Configuration

All configuration comes from environment variables. No
credentials are hardcoded. `APP_ENV` selects `development` / `test` /
`production` settings.

## Adding a new MCP server

1. Copy any existing server directory (e.g. `invoice-mcp/`).
2. Implement only the `tools/`, `services/`, `repository/` (and any new
   `connectors/`) for the new capability.
3. Everything else — bootstrap, logging, config, exceptions, response
   envelopes, Docker layout — is reused unchanged from `shared/`.
