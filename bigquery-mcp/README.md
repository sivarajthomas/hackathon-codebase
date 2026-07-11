# bigquery-mcp server

A BigQuery MCP server built on the [MCP Toolbox for Databases](https://github.com/googleapis/genai-toolbox).

Unlike the other servers in this platform (which are custom Python services), this
server runs Google's Toolbox binary. It exposes **all of Google's prebuilt BigQuery
tools** plus a few **custom tools** defined in [tools.yaml](tools.yaml).

## Tools

### Prebuilt (same as `toolbox --prebuilt bigquery`)

| Tool | Purpose |
|------|---------|
| `execute_sql` | Execute an arbitrary SQL statement. |
| `list_dataset_ids` | List datasets in the project. |
| `list_table_ids` | List tables in a dataset. |
| `get_dataset_info` | Get dataset metadata. |
| `get_table_info` | Get table metadata (schema). |
| `search_catalog` | Find tables, views, models, routines or connections. |
| `analyze_contribution` | Contribution analysis on key metric changes. |
| `ask_data_insights` | Conversational analytics over BigQuery tables. |
| `forecast` | Forecast time-series data. |

### Custom (added on top)

| Tool | Purpose |
|------|---------|
| `preview_table` | Return the first N rows of a table. |
| `count_rows` | Count rows in a table. |
| `table_storage_info` | Row counts and storage sizes for tables in a dataset. |

Toolsets (`default`, `data`, `analytics`, `custom`) are defined at the bottom of
[tools.yaml](tools.yaml) so clients can expose a subset.

## Setup

1. **Toolbox binary** — `toolbox.exe` (v1.6.0, Windows amd64) is already
   downloaded into this folder. For other platforms grab it from the
   [releases page](https://github.com/googleapis/mcp-toolbox/releases).

2. **Authenticate to Google Cloud.** This setup uses a service-account key
   (`GOOGLE_APPLICATION_CREDENTIALS` in [../.vscode/mcp.json](../.vscode/mcp.json)).
   Alternatively use Application Default Credentials:

   ```powershell
   gcloud auth application-default login
   ```

3. **Config is ready.** [../.vscode/mcp.json](../.vscode/mcp.json) already points
   at the binary, `tools.yaml`, and the `gcp-eds-finance-user-dev` project. The
   supported environment variables are documented at the top of [tools.yaml](tools.yaml).

## Run standalone

```powershell
./toolbox.exe --config ./bigquery-mcp/tools.yaml --stdio
```

Serve over HTTP instead of stdio:

```powershell
./toolbox.exe --config ./bigquery-mcp/tools.yaml --address 127.0.0.1 --port 5000
```

## Security notes

- Custom tools parameterize row data with bound query parameters (`@name`).
- Dataset/table identifiers use `templateParameters`, which cannot be bound
  parameters in SQL. Only expose this server to trusted callers, and consider
  setting `BIGQUERY_MAXIMUM_BYTES_BILLED` to bound query cost.
