"""Frontend backend-for-frontend (BFF) for Cloud Run.

Serves a minimal chat UI and proxies questions to the orchestrator's ``/ask``
endpoint. Because the orchestrator is deployed with ``--no-allow-unauthenticated``,
a browser cannot call it directly; this BFF mints a Google identity token
server-side (audience = orchestrator root URL) and forwards the request.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).parent / "static"


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ORCHESTRATOR_URL = _get("ORCHESTRATOR_URL").rstrip("/")
USE_AUTH = _get_bool("USE_AUTH", True)
REQUEST_TIMEOUT = float(_get("REQUEST_TIMEOUT", "180"))
PORT = int(_get("PORT", "8080"))

app = FastAPI(title="MCP Chat Frontend", version="1.0.0")


def _auth_headers() -> dict[str, str]:
    """Mint a Google identity token for the orchestrator (Cloud Run IAM)."""
    if not USE_AUTH:
        return {}
    import google.auth.transport.requests
    import google.oauth2.id_token

    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, ORCHESTRATOR_URL)
    return {"Authorization": f"Bearer {token}"}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """Serve the chat UI."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/api/ask")
async def ask(payload: dict[str, Any]) -> Any:
    """Proxy a question to the orchestrator, attaching an identity token."""
    if not ORCHESTRATOR_URL:
        raise HTTPException(status_code=503, detail="ORCHESTRATOR_URL is not configured.")
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="A non-empty 'question' is required.")

    body: dict[str, Any] = {"question": question}
    if payload.get("force_servers"):
        body["force_servers"] = payload["force_servers"]

    try:
        headers = _auth_headers()
    except Exception as exc:  # token minting failed
        raise HTTPException(status_code=500, detail=f"Auth token error: {exc}") from exc

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/ask", json=body, headers=headers
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Orchestrator unreachable: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# Serve additional static assets (if any) under /static.
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def main() -> None:
    """Run with uvicorn (Cloud Run binds via PORT)."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_config=None)  # noqa: S104


if __name__ == "__main__":
    main()
