"""Feedback loop + audit logging.

Closes the loop for every CS decision: writes an audit record, updates the
Finding status, and (placeholder) forwards the signal to the Prevent pipeline
and the router/prompt-tuning dataset.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .gcp import GCPClients
from .schemas import FindingStatus, ReasonCode, ReviewDecision


_DECISION_TO_STATUS: dict[ReviewDecision, FindingStatus] = {
    ReviewDecision.ACCEPT: FindingStatus.RESOLVED,
    ReviewDecision.MODIFY: FindingStatus.RESOLVED,
    ReviewDecision.REJECT: FindingStatus.REJECTED,
}


class FeedbackService:
    def __init__(self, gcp: GCPClients) -> None:
        self.gcp = gcp

    async def record(
        self,
        trace_id: str,
        decision: ReviewDecision,
        reason_code: ReasonCode,
        reviewer_id: str,
        finding_id: Optional[str],
        output: Optional[dict[str, Any]],
        comment: Optional[str] = None,
    ) -> FindingStatus:
        status = _DECISION_TO_STATUS.get(decision, FindingStatus.IN_REVIEW)

        audit_record = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "reason_code": reason_code.value,
            "finding_id": finding_id,
            "comment": comment,
            "recommendation": output,
        }
        await self.gcp.write_audit_log(audit_record)

        if finding_id:
            await self.gcp.update_finding_status(finding_id, status)

        # TODO(placeholder): publish to the Prevent pipeline + append to the
        #   router/prompt-tuning dataset (e.g. Pub/Sub topic or BigQuery table).
        return status
