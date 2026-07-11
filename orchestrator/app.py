"""Orchestrator FastAPI app (Cloud Run entry point).

Pipeline for each request:

    question
      -> router (Gemini 2.5 Flash): complexity + target MCP server(s)
      -> model selection by complexity
      -> agent: grounded tool-calling loop against the chosen MCP server(s)
      -> natural-language answer + actual proof (raw tool results)
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import get_settings
from schemas import AskRequest, AskResponse, RoutingInfo
from services import agent, router

try:
    from shared.logging import bind_request_id, configure_logging, get_logger

    _HAS_SHARED = True
except Exception:  # pragma: no cover
    import logging as _logging

    _HAS_SHARED = False

    def configure_logging(**_kwargs) -> None:  # type: ignore[no-redef]
        _logging.basicConfig(level=_logging.INFO)

    def get_logger(name: str):  # type: ignore[no-redef]
        return _logging.getLogger(name)

    def bind_request_id(request_id=None):  # type: ignore[no-redef]
        return request_id or str(uuid.uuid4())


settings = get_settings()
configure_logging(level=settings.log_level, service_name="orchestrator")
logger = get_logger(__name__)

app = FastAPI(title="MCP Orchestrator", version="1.0.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> JSONResponse:
    """Readiness probe: verifies core configuration is present."""
    problems: list[str] = []
    if not settings.project_id:
        problems.append("GCP_PROJECT is not set")
    if not settings.targets():
        problems.append("No MCP server URLs configured (INVOICE_MCP_URL/BIGQUERY_MCP_URL)")
    status = 200 if not problems else 503
    return JSONResponse(status_code=status, content={"ready": not problems, "problems": problems})


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """Analyze, route, and answer a user question via the MCP servers."""
    request_id = bind_request_id(payload.session_id)
    targets_by_key = settings.targets()
    if not targets_by_key:
        raise HTTPException(status_code=503, detail="No MCP servers are configured.")

    # 1. Route (complexity + servers), honouring an explicit override.
    if payload.force_servers:
        chosen = [s for s in payload.force_servers if s in targets_by_key]
        decision = router.RouterDecision(
            complexity="moderate", servers=chosen or list(targets_by_key), reason="override"
        )
        decision.servers = chosen or list(targets_by_key)
    else:
        decision = await router.route(payload.question)

    # 2. Select the model by complexity.
    model = settings.model_for(decision.complexity)

    # 3. Resolve targets and run the grounded agent loop.
    targets = [targets_by_key[k] for k in decision.servers if k in targets_by_key]
    logger.info(
        "Answering question",
        extra={
            "request_id": request_id,
            "complexity": decision.complexity,
            "servers": decision.servers,
            "model": model,
        },
    )
    result = await agent.answer(payload.question, model, targets)

    return AskResponse(
        answer=result.answer,
        model_used=model,
        routing=RoutingInfo(
            complexity=decision.complexity, servers=decision.servers, reason=decision.reason
        ),
        proof=result.proof,
        request_id=request_id,
    )


def main() -> None:
    """Run the app with uvicorn (Cloud Run binds via the PORT env var)."""
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
