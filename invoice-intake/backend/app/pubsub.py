"""Pub/Sub publisher.

The create-invoice flow publishes the payload to a real Pub/Sub topic; a push
subscription delivers it to POST /prevent/pubsub, which runs the Prevent worker.
Publishing fails soft (logs a warning) so the invoice write still succeeds even
if the topic is misconfigured.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from .config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _publisher():
    from google.cloud import pubsub_v1

    return pubsub_v1.PublisherClient()


async def publish(settings: Settings, payload: dict[str, Any]) -> bool:
    """Publish a JSON payload to the configured topic. Returns True on success."""
    if not settings.pubsub_configured():
        logger.warning(
            "Pub/Sub not configured (topic=%s); skipping publish for invoice=%s",
            settings.pubsub_topic, payload.get("invoice_number"),
        )
        return False
    try:
        import asyncio

        client = _publisher()
        topic_path = client.topic_path(settings.gcp_project_id, settings.pubsub_topic)
        data = json.dumps(payload).encode("utf-8")

        def _pub() -> str:
            future = client.publish(topic_path, data)
            return future.result(timeout=30)

        msg_id = await asyncio.to_thread(_pub)
        logger.info("Published to Pub/Sub topic=%s msg_id=%s invoice=%s",
                    settings.pubsub_topic, msg_id, payload.get("invoice_number"))
        return True
    except Exception as exc:
        logger.warning("Pub/Sub publish failed for invoice=%s: %s",
                       payload.get("invoice_number"), exc)
        return False
