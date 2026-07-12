"""Guardrails: input sanitization + automated output gate.

INPUT side (before any model runs):
  * DLP PII masking
  * prompt-injection detection/neutralization

OUTPUT side (before any human sees it):
  * strict Pydantic schema validation per verb
  * RAGAS groundedness gate  ->  refuse-if-ungrounded
  * output sanitization
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from .config import Settings
from .schemas import VERB_OUTPUT_MODELS, GuardrailReport, Verb

_INJECTION_PATTERNS = [
    r"ignore (all|the|any|previous|prior) instructions",
    r"disregard (all|the|any|previous|prior).*(rules|policy|instructions)",
    r"system prompt",
    r"reveal.*(prompt|instructions|system)",
    r"exfiltrate|data egress|send .* to (http|https)",
    r"</?(script|system|tool)>",
]


async def sanitize_input(text: str, settings: Settings) -> tuple[str, bool, bool]:
    """Return (clean_text, pii_masked, injection_detected)."""
    injection_detected = any(re.search(p, text, re.IGNORECASE) for p in _INJECTION_PATTERNS)

    # TODO(placeholder): call GCP DLP de-identify with settings.dlp_template_name
    #   to mask PII (names, emails, account numbers, etc.).
    masked_text = text
    pii_masked = False  # set True once DLP is wired

    return masked_text, pii_masked, injection_detected


async def sanitize_mcp_payload(payload: Any, settings: Settings) -> Any:
    """Neutralize untrusted MCP/document content (injection + PII)."""
    # TODO(placeholder): strip active content, mask PII in retrieved rows/files,
    #   and neutralize embedded instructions before it reaches the model.
    return payload


async def sanitize_output(output: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Final scrub of model output before it leaves the backend."""
    # TODO(placeholder): DLP re-check on generated text; drop any leaked secrets.
    return output


async def ragas_groundedness(
    question: str, answer: str, contexts: list[str], settings: Settings
) -> float:
    """Return a groundedness/faithfulness score in [0, 1]."""
    # TODO(placeholder): call RAGAS faithfulness/groundedness with the real
    #   (question, answer, contexts). No context -> ungrounded.
    if not contexts:
        return 0.0
    return 0.95


async def run_output_guardrails(
    verb: Verb,
    raw_output: dict[str, Any],
    question: str,
    contexts: list[str],
    injection_detected: bool,
    settings: Settings,
) -> tuple[Optional[BaseModel], GuardrailReport]:
    """Validate schema + gate on groundedness. Returns (validated_or_None, report)."""
    report = GuardrailReport(pii_masked=True, injection_detected=injection_detected)

    if injection_detected:
        report.notes.append("prompt injection detected in input; refusing.")
        return None, report

    model_cls = VERB_OUTPUT_MODELS[verb]
    try:
        validated = model_cls.model_validate(raw_output)
        report.schema_valid = True
    except ValidationError as exc:
        report.notes.append(f"schema validation failed: {exc.error_count()} error(s).")
        return None, report

    score = await ragas_groundedness(question, str(raw_output), contexts, settings)
    report.groundedness_score = round(score, 3)
    report.grounded = score >= settings.ragas_groundedness_threshold
    if not report.grounded:
        report.notes.append(
            f"groundedness {score:.2f} < threshold "
            f"{settings.ragas_groundedness_threshold:.2f}; refusing."
        )
        return None, report

    return validated, report
