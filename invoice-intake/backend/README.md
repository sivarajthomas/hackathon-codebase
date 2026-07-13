# Invoice Intake (Prevent producer)

A standalone vertical-slice service that lets an operator enter a new invoice in
real time and writes it to every relevant table with validation. It then
pre-analyzes the invoice, stages one `analyzed_data` row, and **publishes a
PreventPayload to Pub/Sub**. The existing **Prevent agent** (main backend,
`POST /v1/prevent/pubsub`) is the single consumer that reasons over the analyzed
data and writes findings for customer-support review.

This service is **independent** of the main backend and does **not** consume
messages, write findings, or change the Prevent agent's explanation behaviour.

```
invoice-intake/
  backend/        FastAPI service (intake + publish only)
    app/
      main.py            HTTP endpoints
      intake.py          validation, cross-table writes, dup checks, pre-analysis
      leakage.py         deterministic leakage calculator (numbers only)
      store.py           BigQuery writes/reads with in-memory fallback
      tables.py          table registry (drives the dynamic form)
      pubsub.py          real Pub/Sub publish
      config.py          settings
      schemas.py         request/response models
      logging_setup.py   Cloud Run JSON logs
  frontend/       Vite + React UI (dynamic intake form)
```

## Flow

1. Operator fills the **Create Invoice** form (shipment + charges).
2. `POST /invoices` validates both records, mints `SHP…`/`INV…` ids, rejects
   duplicates (HTTP 409) and invalid fields (HTTP 422), then writes
   `shipment_transactions` + `invoice_records`.
3. It computes the deterministic expected-vs-billed breakdown and stages one
   `analyzed_data` row (the Prevent agent's input), then **publishes a
   PreventPayload** `{invoice_number, analyzed_data_ref, contract_ids, geo,
   currency}` to the topic.
4. A push subscription delivers the message to the Prevent agent
   (`POST /v1/prevent/pubsub`), which reads `analyzed_data`, reasons over it, and
   writes the finding. Flagged invoices then appear in the **Prevent section of
   the main app** for CS review.

BigQuery / Pub/Sub are optional locally: with neither configured the service
uses an in-memory store and skips publishing (the create response still returns
the staged leakage summary).

## Run locally

```powershell
# backend
Set-Location invoice-intake/backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# frontend (new terminal)
Set-Location invoice-intake/frontend
npm install
$env:VITE_API_BASE="http://localhost:8080"; npm run dev
```

## Configuration (env vars)

| Variable            | Purpose                                             |
| ------------------- | --------------------------------------------------- |
| `GCP_PROJECT_ID`    | Project for BigQuery / Pub/Sub / Vertex.            |
| `GCP_LOCATION`      | Vertex location (default `us-central1`).            |
| `BIGQUERY_DATASET`  | Dataset holding the tables. Unset ⇒ in-memory.      |
| `PUBSUB_TOPIC`      | Topic the intake publishes to. Unset ⇒ no publish.  |
| `DEFAULT_CURRENCY`  | Currency stamped on the payload (default `INR`).    |
| `LOG_LEVEL`         | `INFO` by default.                                  |

If a value is unset (or left as `REPLACE_ME`) the corresponding integration is
skipped and the in-memory / deterministic path is used.

## Deploy to Cloud Run

```powershell
# backend
Set-Location invoice-intake/backend
gcloud builds submit --config cloudbuild.yaml --substitutions=_REGION=us-central1

# set runtime config
gcloud run services update invoice-intake-backend --region us-central1 `
  --set-env-vars GCP_PROJECT_ID=<proj>,BIGQUERY_DATASET=<ds>,PUBSUB_TOPIC=<topic>

# point a Pub/Sub push subscription at the PREVENT AGENT (main backend),
# NOT this service — this service only publishes.
gcloud pubsub subscriptions create invoice-prevent-sub `
  --topic <topic> --push-endpoint https://<main-backend-url>/v1/prevent/pubsub `
  --push-auth-service-account prevent-push@<proj>.iam.gserviceaccount.com

# frontend (bake in this backend's URL)
Set-Location ../frontend
gcloud builds submit --config cloudbuild.yaml `
  --substitutions=_API_BASE=https://<backend-url>
```
