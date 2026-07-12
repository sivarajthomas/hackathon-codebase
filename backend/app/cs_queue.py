"""Customer-support (CS) work queue.

Actionable outputs (Resolve, Prevent) that require human approval are enqueued
here so they surface in the CS person's queue in the frontend. Prevent findings
are ALSO persisted to a BigQuery data store (see `GCPClients.store_prevent_finding`).

TODO(placeholder): back this with Firestore / Pub/Sub / Cloud Tasks so the queue
is durable, shared across instances, and the frontend can poll or subscribe.
"""

from __future__ import annotations

from typing import Optional

from .schemas import CSQueueTask

# In-memory queue. TODO(placeholder): replace with a durable backing store.
_QUEUE: dict[str, CSQueueTask] = {}


class CSQueueService:
    async def enqueue(self, task: CSQueueTask) -> str:
        # TODO(placeholder): publish to the real CS queue (settings.cs_queue_backend).
        _QUEUE[task.task_id] = task
        return task.task_id

    async def list_open(self, assignee: Optional[str] = None) -> list[CSQueueTask]:
        tasks = sorted(_QUEUE.values(), key=lambda t: t.created_at)
        if assignee:
            tasks = [t for t in tasks if t.assignee == assignee]
        return tasks

    async def get(self, task_id: str) -> Optional[CSQueueTask]:
        return _QUEUE.get(task_id)

    async def resolve_trace(self, trace_id: str) -> None:
        """Remove any queued task tied to this trace once a CS decision is recorded."""
        for task_id, task in list(_QUEUE.items()):
            if task.trace_id == trace_id:
                _QUEUE.pop(task_id, None)
