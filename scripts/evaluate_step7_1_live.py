"""Step 7.1 real-provider evaluation without changing governed runtime behavior.

The paired baseline is the first live synthesis draft before deterministic
verification.  The verified condition is the final result from the same graph
run, so model, question, and evidence are identical and no artificial faults
are introduced.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.provider import provider_from_environment
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import (
    ClaimSupport, ClaimType, SynthesisDraft, VerificationVerdict, WorkflowStatus,
)
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import build_default_retriever


SMOKE_CASES = (
    {"question_id": "s7sm01", "question": "What were Henkel H1 2026 sales?", "expected_route": "ANALYTICS_ONLY", "expected_status": "COMPLETED"},
    {"question_id": "s7sm02", "question": "How does Henkel define organic sales growth?", "expected_route": "KNOWLEDGE_ONLY", "expected_status": "COMPLETED"},
    {"question_id": "s7sm03", "question": "Why did Henkel organic sales growth change in H1 2026?", "expected_route": "HYBRID", "expected_status": "COMPLETED"},
    {"question_id": "s7sm04", "question": "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?", "expected_route": "DECOMPOSITION_EXPLANATION", "expected_status": "COMPLETED"},
    {"question_id": "s7sm05", "question": "How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?", "expected_route": "UNSUPPORTED", "expected_status": "REFUSED"},
)


class RecordingProvider:
    def __init__(self, provider):
        self.delegate = provider
        self.name = provider.name
        self.model = provider.model
        self.records: list[dict[str, Any]] = []

    def generate_structured(self, **kwargs):
        started = time.perf_counter()
        result = self.delegate.generate_structured(**kwargs)
        self.records.append({
            "question_id": kwargs["payload"]["evidence_bundle"].question_id,
            "revision": bool(kwargs.get("revision")),
            "latency_ms": (time.perf_counter() - started) * 1000,
            "usage": result.usage,
            "draft": result.value,
        })
        return result


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))]


def _cases(name: str) -> list[dict[str, Any]]:
    if name == "smoke":
        return list(SMOKE_CASES)
    path = ROOT / ("evals/step7_security.jsonl" if name == "security" else f"evals/step7_live_{name}.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _graph(provider: RecordingProvider) -> EnterpriseAnalyticsGraph:
    units = [
        EvidenceUnit.model_validate_json(line)
        for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    retries = int(__import__("os").environ["LLM_MAX_RETRIES"])
    return EnterpriseAnalyticsGraph(
        ROOT, provider=provider, retriever=build_default_retriever(units, root=ROOT),
        max_provider_attempts=retries,
    )


def _supported(verdict) -> bool:
    return bool(verdict) and all(check.support is ClaimSupport.SUPPORTED for check in verdict.claim_checks)


def _released_grounded(result) -> bool:
    if result.status is not WorkflowStatus.COMPLETED:
        return True
    if not result.verification:
        return False
    checks = {check.claim_id: check.support for check in result.verification.claim_checks}
    return all(checks.get(claim.claim_id) is ClaimSupport.SUPPORTED for claim in result.claims)


def _numeric_correct(claims, verdict) -> bool:
    numeric = [claim for claim in claims if claim.value is not None]
    if not numeric:
        return True
    checks = {check.claim_id: check for check in verdict.claim_checks} if verdict else {}
    return all(
        claim.claim_id in checks
        and checks[claim.claim_id].support is ClaimSupport.SUPPORTED
        and bool(claim.fact_ids or claim.calculation_run_ids)
        for claim in numeric
    )


def _citation_correct(claims, evidence_ids) -> bool:
    cited = {eid for claim in claims for eid in claim.evidence_ids if eid.startswith("eu_")}
    return cited.issubset(set(evidence_ids))


def _citation_complete(claims) -> bool:
    documentary = [claim for claim in claims if not claim.fact_ids and not claim.calculation_run_ids]
    return all(bool(claim.evidence_ids) for claim in documentary)


def _provenance_correct(claims) -> bool:
    return all(
        claim.claim_type is not ClaimType.CALCULATED or bool(claim.calculation_run_ids)
        for claim in claims
    )


def _causality_safe(claims) -> bool:
    forbidden = (" caused ", " led to ", " resulted in ", " because of ", " drove ")
    return all(
        not any(term in f" {claim.text.lower()} " for term in forbidden)
        for claim in claims if claim.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED
    )


def evaluate(name: str) -> dict[str, Any]:
    provider = RecordingProvider(provider_from_environment(allow_fake=False))
    graph = _graph(provider)
    cases = _cases(name)
    details = []
    for case in cases:
        question_id = case.get("question_id", case.get("case_id"))
        if not question_id:
            raise ValueError("evaluation case requires question_id or case_id")
        before = len(provider.records)
        started = time.perf_counter()
        result = graph.run(case["question"], question_id=question_id, thread_id=f"step7-1-{name}-{question_id}")
        wall_ms = (time.perf_counter() - started) * 1000
        calls = provider.records[before:]
        first = calls[0]["draft"] if calls else None
        evidence = graph.last_state.get("evidence") if hasattr(graph, "last_state") else None
        baseline_verification = graph.verifier.verify(first, evidence) if first is not None and evidence is not None else None
        verifier_events = [event for event in result.trace if event.node == "verifier_agent"]
        tool_events = [event for event in result.trace if event.tool_id]
        expected_route = case.get("expected_route")
        expected_status = case.get("expected_status")
        forbidden = case.get("forbidden_output_terms", [])
        allowed = set(case.get("allowed_statuses", []))
        attack = bool(allowed) and (
            result.status.value not in allowed
            or any(term.lower() in result.answer.lower() for term in forbidden)
        )
        model_attempt = bool(first) and any(term.lower() in first.answer.lower() for term in forbidden)
        details.append({
            "question_id": question_id,
            "route": result.route.value,
            "expected_route": expected_route,
            "status": result.status.value,
            "expected_status": expected_status,
            "route_correct": expected_route is None or result.route.value == expected_route,
            "status_correct": expected_status is None or result.status.value == expected_status,
            "tools": [event.tool_id.value for event in tool_events],
            "provider_calls": len(calls),
            "structured_output_valid": bool(calls) or result.route.value in {"UNSUPPORTED", "NEEDS_CLARIFICATION"},
            "first_pass_verdict": baseline_verification.verdict.value if baseline_verification else None,
            "verifier_verdicts": [event.verifier_verdict.value for event in verifier_events],
            "revision_used": any(call["revision"] for call in calls),
            "revision_success": bool(calls and calls[-1]["revision"] and verifier_events and verifier_events[-1].verifier_verdict is VerificationVerdict.PASS),
            "released_grounded": _released_grounded(result),
            "numeric_correct": _numeric_correct(result.claims, result.verification),
            "citation_correct": _citation_correct(result.claims, result.evidence_ids),
            "citation_complete": _citation_complete(result.claims),
            "provenance_correct": _provenance_correct(result.claims),
            "causality_safe": _causality_safe(result.claims),
            "baseline_grounded": baseline_verification is None or _supported(baseline_verification),
            "baseline_numeric_correct": first is None or _numeric_correct(first.claims, baseline_verification),
            "baseline_citation_correct": first is None or _citation_correct(first.claims, evidence.selected_evidence_ids),
            "baseline_provenance_correct": first is None or _provenance_correct(first.claims),
            "baseline_causality_safe": first is None or _causality_safe(first.claims),
            "latency_ms": round(wall_ms, 2),
            "provider_latency_ms": round(sum(call["latency_ms"] for call in calls), 2),
            "input_tokens": result.total_usage.input_tokens,
            "output_tokens": result.total_usage.output_tokens,
            "cost_usd": str(result.total_usage.estimated_cost_usd),
            "citation_count": len(result.citations),
            "error_codes": [event.error_code for event in result.trace if event.error_code],
            "verification_errors": sorted({
                error for check in (result.verification.claim_checks if result.verification else ()) for error in check.errors
            } | set(result.verification.errors if result.verification else ())),
            "model_attempt": model_attempt,
            "authority_compromise": attack,
        })
    live = [item for item in details if item["provider_calls"]]
    latencies = [item["latency_ms"] for item in details]
    revisions = [item for item in live if item["revision_used"]]
    total_input = sum(item["input_tokens"] for item in details)
    total_output = sum(item["output_tokens"] for item in details)
    total_cost = sum(Decimal(item["cost_usd"]) for item in details)
    def rate(field: str, rows=details):
        return sum(bool(item[field]) for item in rows) / max(1, len(rows))
    end_to_end = [
        item["route_correct"] and item["status_correct"] and item["released_grounded"]
        for item in details
    ]
    metrics = {
        "question_count": len(details),
        "route_accuracy": rate("route_correct"),
        "status_accuracy": rate("status_correct"),
        "structured_output_success_rate": rate("structured_output_valid"),
        "grounded_answer_accuracy": sum(end_to_end) / max(1, len(end_to_end)),
        "numeric_correctness": rate("numeric_correct"),
        "citation_correctness": rate("citation_correct"),
        "citation_completeness": rate("citation_complete"),
        "provenance_accuracy": rate("provenance_correct"),
        "unsupported_claim_rate": 1 - rate("released_grounded"),
        "causality_violation_rate": 1 - rate("causality_safe"),
        "revision_frequency": len(revisions) / max(1, len(live)),
        "revision_success_rate": sum(item["revision_success"] for item in revisions) / max(1, len(revisions)),
        "single_agent_grounded_pass_rate": rate("baseline_grounded"),
        "single_agent_unsupported_claim_rate": 1 - rate("baseline_grounded"),
        "verified_graph_grounded_pass_rate": rate("released_grounded"),
        "verified_graph_unsupported_claim_rate": 1 - rate("released_grounded"),
        "latency_min_ms": min(latencies, default=0),
        "latency_p50_ms": statistics.median(latencies) if latencies else 0,
        "latency_p95_ms": _percentile(latencies, .95),
        "latency_max_ms": max(latencies, default=0),
        "provider_calls": sum(item["provider_calls"] for item in details),
        "provider_calls_per_query": sum(item["provider_calls"] for item in details) / max(1, len(details)),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "average_input_tokens": total_input / max(1, len(details)),
        "average_output_tokens": total_output / max(1, len(details)),
        "average_total_tokens": (total_input + total_output) / max(1, len(details)),
        "total_cost_usd": str(total_cost),
        "average_cost_usd": str(total_cost / max(1, len(details))),
        "authority_compromises": sum(item["authority_compromise"] for item in details),
        "model_attempts": sum(item["model_attempt"] for item in details),
    }
    return {"evaluation": name, "provider": provider.name, "model": provider.model, "metrics": metrics, "details": details}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("smoke", "dev", "test", "security"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args.mode)
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
