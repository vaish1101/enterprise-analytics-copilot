from __future__ import annotations

from collections import Counter
from decimal import Decimal
from threading import Lock


class MetricsStore:
    def __init__(self):
        self._lock = Lock()
        self.counters = Counter()
        self.routes = Counter()

    def record(self, response) -> None:
        with self._lock:
            self.counters["requests"] += 1
            self.counters[response.status.lower()] += 1
            if response.status not in {"COMPLETED", "REFUSED", "NEEDS_CLARIFICATION"}:
                self.counters["errors"] += 1
            self.counters["revisions"] += int(response.execution.revision_used)
            self.counters["provider_calls"] += response.execution.provider_calls or 0
            self.counters["provider_calls_unknown"] += int(response.execution.provider_calls is None)
            self.counters["input_tokens"] += response.execution.input_tokens
            self.counters["output_tokens"] += response.execution.output_tokens
            self.counters["latency_ms"] += response.latency_ms
            self.counters["cost_usd"] += Decimal(response.execution.cost_usd)
            self.routes[response.route] += 1
            verdict = response.verification.verdict if response.verification else "NOT_APPLICABLE"
            self.counters[f"verifier:{verdict}"] += 1

    def record_error(self) -> None:
        with self._lock:
            self.counters["requests"] += 1
            self.counters["errors"] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "requests": self.counters["requests"],
                "completed": self.counters["completed"],
                "refused": self.counters["refused"],
                "clarification": self.counters["needs_clarification"],
                "errors": self.counters["errors"],
                "revisions": self.counters["revisions"],
                "provider_calls": None if self.counters["provider_calls_unknown"] else self.counters["provider_calls"],
                "input_tokens": self.counters["input_tokens"],
                "output_tokens": self.counters["output_tokens"],
                "estimated_cost_usd": str(self.counters["cost_usd"]),
                "average_latency_ms": round(self.counters["latency_ms"] / self.counters["requests"], 2) if self.counters["requests"] else 0,
                "route_distribution": dict(self.routes),
                "verifier_distribution": {
                    key.removeprefix("verifier:"): value
                    for key, value in self.counters.items() if key.startswith("verifier:")
                },
            }
