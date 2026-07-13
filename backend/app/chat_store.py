"""In-memory chat-history + invoice-metadata stores (placeholders).

Mirrors the BigQuery ``conversations`` / ``messages`` / ``invoice_metadata``
tables from the design so the full multi-session + traceability flow runs
end-to-end in dev. Swap these functions for real BigQuery reads/writes later;
callers depend only on the function signatures here.

All conversation/message access is scoped by ``user_id`` to prevent cross-user
data leakage (IDOR).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from .schemas import (
    ConversationDetail,
    ConversationSummary,
    EvidenceItem,
    InvoiceContext,
    MessageRecord,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- #
# Conversations + messages
# --------------------------------------------------------------------------- #
# conversation_id -> conversation dict; messages held on the conversation.
_CONVERSATIONS: dict[str, dict[str, Any]] = {}


def create_conversation(
    user_id: str, agent: str, invoice_number: Optional[str], title: Optional[str] = None
) -> ConversationSummary:
    conv_id = _new_id("cv")
    now = _utcnow()
    conv = {
        "conversation_id": conv_id,
        "user_id": user_id,
        "agent": agent,
        "invoice_number": invoice_number,
        "title": title or "New conversation",
        "message_count": 0,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _CONVERSATIONS[conv_id] = conv
    return _summary(conv)


def _summary(conv: dict[str, Any]) -> ConversationSummary:
    return ConversationSummary(
        conversation_id=conv["conversation_id"],
        user_id=conv["user_id"],
        agent=conv["agent"],
        invoice_number=conv.get("invoice_number"),
        title=conv.get("title", "New conversation"),
        message_count=conv.get("message_count", 0),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
    )


def get_conversation(conv_id: str, user_id: str) -> Optional[ConversationDetail]:
    conv = _CONVERSATIONS.get(conv_id)
    if conv is None or conv["is_deleted"] or conv["user_id"] != user_id:
        return None
    return ConversationDetail(
        **{k: v for k, v in _summary(conv).model_dump().items()},
        messages=[MessageRecord(**m) for m in conv["messages"]],
    )


def list_conversations(
    user_id: str,
    q: Optional[str] = None,
    agent: Optional[str] = None,
    invoice_number: Optional[str] = None,
    limit: int = 50,
) -> list[ConversationSummary]:
    rows: list[dict[str, Any]] = []
    needle = (q or "").strip().lower()
    for conv in _CONVERSATIONS.values():
        if conv["is_deleted"] or conv["user_id"] != user_id:
            continue
        if agent and conv["agent"] != agent:
            continue
        if invoice_number and conv.get("invoice_number") != invoice_number:
            continue
        if needle:
            haystack = " ".join(
                [
                    conv.get("title", ""),
                    conv.get("invoice_number") or "",
                    *[(m.get("question") or "") + " " + (m.get("response") or "") for m in conv["messages"]],
                ]
            ).lower()
            if needle not in haystack:
                continue
        rows.append(conv)
    rows.sort(key=lambda c: c["updated_at"], reverse=True)
    return [_summary(c) for c in rows[:limit]]


def append_message(
    conv_id: str,
    user_id: str,
    role: str,
    *,
    question: Optional[str] = None,
    response: Optional[str] = None,
    evidence: Optional[list[EvidenceItem]] = None,
    trace_id: Optional[str] = None,
    status: Optional[str] = None,
    set_title_from: Optional[str] = None,
) -> Optional[MessageRecord]:
    conv = _CONVERSATIONS.get(conv_id)
    if conv is None or conv["is_deleted"] or conv["user_id"] != user_id:
        return None
    record = {
        "message_id": _new_id("m"),
        "conversation_id": conv_id,
        "role": role,
        "question": question,
        "response": response,
        "evidence": [e.model_dump() if isinstance(e, EvidenceItem) else e for e in (evidence or [])],
        "trace_id": trace_id,
        "status": status,
        "created_at": _utcnow(),
    }
    conv["messages"].append(record)
    conv["message_count"] = len(conv["messages"])
    conv["updated_at"] = record["created_at"]
    if set_title_from and (not conv.get("title") or conv["title"] == "New conversation"):
        title = set_title_from.strip()
        conv["title"] = (title[:38] + "…") if len(title) > 38 else title
    return MessageRecord(**record)


def soft_delete_conversation(conv_id: str, user_id: str) -> bool:
    conv = _CONVERSATIONS.get(conv_id)
    if conv is None or conv["user_id"] != user_id:
        return False
    conv["is_deleted"] = True
    return True


def delete_all_conversations(user_id: str) -> int:
    count = 0
    for conv in _CONVERSATIONS.values():
        if conv["user_id"] == user_id and not conv["is_deleted"]:
            conv["is_deleted"] = True
            count += 1
    return count


# --------------------------------------------------------------------------- #
# Invoice metadata (placeholder for the BigQuery `invoice_metadata` table)
# --------------------------------------------------------------------------- #
def _seed_invoices() -> dict[str, dict[str, Any]]:
    rows = [
        ("INV0001", date(2025, 7, 1), "u-cust-001", "CTR-1001", ["SHP0001"], "OPEN", None, "USD", 1204.50, "SAP"),
        ("INV0004", date(2025, 7, 3), "u-cust-001", "CTR-1001", ["SHP0004"], "BLOCKED", "payment dispute", "USD", 980.00, "SAP"),
        ("INV0011", date(2025, 7, 6), "u-cust-002", "CTR-1002", ["SHP0011"], "OPEN", "missing discount", "INR", 72000.00, "BigQuery"),
        ("INV0018", date(2025, 7, 9), "u-cust-003", "CTR-1003", ["SHP0018", "SHP0019"], "OPEN", "weight dispute", "USD", 3320.00, "SAP"),
        ("INV0005", date(2025, 7, 4), "u-cust-005", "CTR-1005", ["SHP0005"], "PAID", None, "USD", 640.00, "BigQuery"),
    ]
    store: dict[str, dict[str, Any]] = {}
    for inv, idate, cust, ctr, ships, st, disp, cur, total, src in rows:
        store[inv] = {
            "invoice_number": inv,
            "invoice_date": idate,
            "customer_id": cust,
            "contract_number": ctr,
            "shipment_ids": ships,
            "status": st,
            "dispute_reason": disp,
            "currency": cur,
            "total_amount": total,
            "source_system": src,
            "last_updated": "2025-08-01T00:00:00Z",
        }
    return store


_INVOICES: dict[str, dict[str, Any]] = _seed_invoices()


def get_invoice_context(
    invoice_number: str, contract_ids: Optional[list[str]] = None
) -> Optional[InvoiceContext]:
    """Return denormalised invoice context, enforcing contract-scope access.

    ``contract_ids`` is the caller's row-level-security scope. An empty scope
    (e.g. customer-support users) sees every invoice. A non-empty scope only
    sees invoices whose ``contract_number`` is in that scope.
    """
    row = _INVOICES.get((invoice_number or "").strip().upper())
    if row is None:
        return None
    if contract_ids and row.get("contract_number") not in contract_ids:
        # Out of scope -> treat as not accessible (handled as 403 by the route).
        raise PermissionError(invoice_number)
    return InvoiceContext(exists=True, **row)
