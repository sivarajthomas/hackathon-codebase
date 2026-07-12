"""Per-stage tracing + latency SLO helper.

Wrap every pipeline stage with `async with trace.stage("name"):` so we capture
per-stage latency. Replace the placeholder export with Cloud Trace / OpenTelemetry.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from .schemas import StageSpan


@dataclass
class Trace:
    trace_id: str
    spans: list[StageSpan] = field(default_factory=list)
    _start: float = field(default_factory=time.perf_counter)

    @asynccontextmanager
    async def stage(self, name: str):
        start = time.perf_counter()
        ok = True
        try:
            yield
        except Exception:
            ok = False
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self.spans.append(StageSpan(name=name, duration_ms=duration_ms, ok=ok))
            # TODO(placeholder): export span to Cloud Trace / OpenTelemetry.

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self._start
