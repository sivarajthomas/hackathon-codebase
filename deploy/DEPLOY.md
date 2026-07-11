# Deploying to Cloud Run via Cloud Build + GitHub

Two MCP servers deploy independently. Each has a self-contained Cloud Build
pipeline that **builds the image, pushes it to Artifact Registry, and deploys
to Cloud Run**:

| Server        | Cloud Build config              | Runtime | Backend |
|---------------|---------------------------------|---------|---------|
| `bigquery-mcp`| `bigquery-mcp/cloudbuild.yaml`  | Google MCP Toolbox binary | BigQuery |
| `invoice-mcp` | `invoice-mcp/cloudbuild.yaml`   | Python FastMCP | Google Cloud Storage |

`toolbox.exe` (271 MB) is **git-ignored** — it is a local Windows helper only.
The BigQuery image downloads the Linux toolbox binary during the build, so the
binary is never committed to GitHub (which rejects files > 100 MB).

---

## One-time setup

```powershell
gcloud config set project gcp-eds-finance-user-dev

# 1. Enable APIs.
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# 2. Create the Artifact Registry repo (the pipelines push here).
gcloud artifacts repositories create mcp-servers `
  --repository-format=docker --location=us-central1 `
  --description="MCP server images"

# 3. Grant the Cloud Build service account permission to deploy Cloud Run.
$PROJECT_NUM = gcloud projects describe gcp-eds-finance-user-dev --format="value(projectNumber)"
$BUILD_SA = "$PROJECT_NUM@cloudbuild.gserviceaccount.com"
gcloud projects add-iam-policy-binding gcp-eds-finance-user-dev --member "serviceAccount:$BUILD_SA" --role roles/run.admin
gcloud projects add-iam-policy-binding gcp-eds-finance-user-dev --member "serviceAccount:$BUILD_SA" --role roles/iam.serviceAccountUser
gcloud projects add-iam-policy-binding gcp-eds-finance-user-dev --member "serviceAccount:$BUILD_SA" --role roles/artifactregistry.writer
```

> If your project uses the newer default (builds run as the Compute Engine
> service account `$PROJECT_NUM-compute@developer.gserviceaccount.com`), grant
> the three roles above to **that** account instead.

### Runtime service-account IAM (what the deployed services need)

Cloud Run runs as the Compute Engine default service account unless you set one.
Grant it only what each server needs:

```powershell
$RUN_SA = "$PROJECT_NUM-compute@developer.gserviceaccount.com"
# bigquery-mcp
gcloud projects add-iam-policy-binding gcp-eds-finance-user-dev --member "serviceAccount:$RUN_SA" --role roles/bigquery.jobUser
gcloud projects add-iam-policy-binding gcp-eds-finance-user-dev --member "serviceAccount:$RUN_SA" --role roles/bigquery.dataViewer
# invoice-mcp (read-only on the knowledge bucket)
gcloud storage buckets add-iam-policy-binding gs://gcp-eds-finance-user-dev_isps_test_config_s --member "serviceAccount:$RUN_SA" --role roles/storage.objectViewer
```

---

## Option A — GitHub-triggered deploys (recommended)

Create one trigger per server, each pointing at that server's cloudbuild file.
Both build with the **repository root** as the workspace, which is exactly what
the configs expect.

```powershell
# Connect the GitHub repo first: Cloud Build > Triggers > Connect Repository.
gcloud builds triggers create github `
  --name=deploy-invoice-mcp `
  --repo-name=<your-repo> --repo-owner=<your-org> `
  --branch-pattern="^main$" `
  --build-config=invoice-mcp/cloudbuild.yaml

gcloud builds triggers create github `
  --name=deploy-bigquery-mcp `
  --repo-name=<your-repo> --repo-owner=<your-org> `
  --branch-pattern="^main$" `
  --build-config=bigquery-mcp/cloudbuild.yaml
```

Push to `main` → each pipeline builds, pushes, and deploys automatically.

## Option B — Manual one-off deploy (from the repo root)

```powershell
gcloud builds submit . --config invoice-mcp/cloudbuild.yaml `
  --substitutions=_REGION=us-central1,_REPO=mcp-servers,_GCS_BUCKET=gcp-eds-finance-user-dev_isps_test_config_s

gcloud builds submit . --config bigquery-mcp/cloudbuild.yaml `
  --substitutions=_REGION=us-central1,_REPO=mcp-servers
```

---

## Configuration knobs (Cloud Build substitutions)

| Substitution | Default | Used by |
|--------------|---------|---------|
| `_REGION`    | `us-central1` | both |
| `_REPO`      | `mcp-servers` | both |
| `_GCS_BUCKET`| `gcp-eds-finance-user-dev_isps_test_config_s` | invoice-mcp |

Environment variables set on the Cloud Run services at deploy time:
- **bigquery-mcp**: `BIGQUERY_PROJECT=$PROJECT_ID`
- **invoice-mcp**: `APP_ENV=production`, `GCP_PROJECT=$PROJECT_ID`, `GCS_BUCKET=<_GCS_BUCKET>`

No secrets or key files are baked into the images — both authenticate with the
Cloud Run runtime service account (Application Default Credentials).

---

## Verify a deployment

Both services deploy with `--no-allow-unauthenticated`, so send an identity token:

```powershell
$URL = gcloud run services describe invoice-mcp --region us-central1 --format "value(status.url)"
$TOKEN = gcloud auth print-identity-token
curl -H "Authorization: Bearer $TOKEN" "$URL/mcp"
```

The MCP endpoint path is `/mcp` for both servers.
