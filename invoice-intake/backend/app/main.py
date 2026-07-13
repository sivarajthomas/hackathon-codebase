"""FastAPI app — Invoice-Intake service (Prevent PRODUCER).

This service owns invoice intake only. After writing the shipment + invoice it
pre-analyzes the invoice (deterministic leakage math), stages one
``analyzed_data`` row, and PUBLISHES a PreventPayload to Pub/Sub. The Prevent
agent (main backend, POST /v1/prevent/pubsub) is the single consumer that reasons
over the analyzed data and writes findings for CS review — this service never
consumes messages or writes findings.

Endpoints
  GET  /health
  GET  /tables                       -> registry metadata (drives the dynamic form)
  GET  /tables/{name}/next-id        -> next prefixed id for a table
  GET  /tables/{name}/rows           -> rows in a table
  POST /tables/{name}                -> generic validated insert into any table
  POST /invoices                     -> create shipment + invoice, stage + publish
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .intake import DuplicateError, Intake, ValidationError
from .logging_setup import configure_logging
from .pubsub import publish
from .schemas import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    GenericRowRequest,
)
from .store import Store
from .tables import REGISTRY

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Intake + Prevent", version="0.1.0")

_origins = [o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singletons (Store keeps the in-memory fallback consistent across calls).
_store: Store | None = None


def get_store(settings: Settings = Depends(get_settings)) -> Store:
    global _store
    if _store is None:
        _store = Store(settings)
    return _store


def get_intake(settings: Settings = Depends(get_settings), store: Store = Depends(get_store)) -> Intake:
    return Intake(settings, store)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Registry metadata (drives the frontend form)
# --------------------------------------------------------------------------- #
@app.get("/tables")
async def list_tables() -> list[dict]:
    return [
        {
            "name": spec.name,
            "label": spec.label or spec.name,
            "key_column": spec.key_column,
            "generates_key": spec.generates_key,
            "key_prefix": spec.key_prefix,
            "part_of_invoice": spec.part_of_invoice,
            "columns": [
                {
                    "name": c.name,
                    "type": c.type,
                    "required": c.required,
                    "ref_table": c.ref_table,
                }
                for c in spec.columns
            ],
        }
        for spec in REGISTRY.values()
    ]


@app.get("/tables/{name}/next-id")
async def next_id(name: str, store: Store = Depends(get_store)) -> dict[str, str]:
    spec = REGISTRY.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown table '{name}'.")
    if not spec.generates_key:
        raise HTTPException(status_code=400, detail=f"Table '{name}' uses a natural key.")
    return {"next_id": await store.next_id(name)}


@app.get("/tables/{name}/rows")
async def table_rows(name: str, limit: int = 200, store: Store = Depends(get_store)) -> list[dict]:
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown table '{name}'.")
    return await store.list_rows(name, limit)


@app.post("/tables/{name}", status_code=201)
async def insert_row(
    name: str, body: GenericRowRequest, intake: Intake = Depends(get_intake)
) -> dict:
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown table '{name}'.")
    try:
        row = await intake.insert_row(name, body.row, body.auto_id)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"table": name, "row": row}


# --------------------------------------------------------------------------- #
# Core intake flow: create shipment + invoice, then publish for Prevent
# --------------------------------------------------------------------------- #
@app.post("/invoices", response_model=CreateInvoiceResponse, status_code=201)
async def create_invoice(
    body: CreateInvoiceRequest,
    settings: Settings = Depends(get_settings),
    intake: Intake = Depends(get_intake),
) -> CreateInvoiceResponse:
    logger.info("POST /invoices auto_id=%s run_prevent=%s", body.auto_id, body.run_prevent)
    try:
        result = await intake.create_invoice(body.shipment, body.invoice, body.auto_id)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc
    except DuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Pre-analyze + stage the analyzed_data row (the Prevent agent's input).
    staged = await intake.stage_for_prevent(result["invoice_number"], result["shipment_id"])

    published = False
    if body.run_prevent:
        # Publish a PreventPayload; the Prevent agent (main backend) consumes it.
        published = await publish(settings, {
            "invoice_number": result["invoice_number"],
            "analyzed_data_ref": staged.get("analyzed_data_ref"),
            "contract_ids": [result["contract_number"]] if result.get("contract_number") else [],
            "geo": settings.default_geo or None,
            "currency": settings.default_currency or None,
        })

    return CreateInvoiceResponse(
        invoice_number=result["invoice_number"],
        shipment_id=result["shipment_id"],
        written_tables=result["written_tables"],
        published=published,
        analyzed_data_ref=staged.get("analyzed_data_ref"),
        anomaly=bool(staged.get("anomaly")),
        leakage_amount=float(staged.get("leakage_amount") or 0.0),
        leakage_type=staged.get("leakage_type"),
        severity=staged.get("severity"),
    )
