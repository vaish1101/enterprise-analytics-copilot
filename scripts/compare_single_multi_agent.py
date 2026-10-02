"""Same-question deterministic comparison of one-pass synthesis and verified graph output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import VerificationVerdict, WorkflowStatus


FAULT_ROTATION = ("wrong_number", "wrong_unit", "wrong_period", "wrong_scope", "wrong_company", "wrong_metric", "provenance_relabel", "calculated_without_lineage")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output"); args = parser.parse_args()
    cases = [json.loads(line) for line in (ROOT / "evals/step6_dev.jsonl").read_text().splitlines() if line]
    eligible = [case for case in cases if case["expected_status"] == "COMPLETED"]
    single_pass = multi_pass = revision_attempts = revision_successes = 0
    single_latency = []; multi_latency = []; single_tokens = multi_tokens = 0
    details = []
    for index, case in enumerate(eligible):
        fault = FAULT_ROTATION[index] if index < len(FAULT_ROTATION) else None
        provider = DeterministicFakeProvider({case["question_id"]: fault} if fault else {})
        graph = EnterpriseAnalyticsGraph(ROOT, provider=provider)
        started = time.perf_counter(); result = graph.run(case["question"], question_id=case["question_id"])
        multi_latency.append((time.perf_counter() - started) * 1000)
        first = provider.generated[0]
        first_verification = graph.verifier.verify(first, graph.last_state["evidence"])
        single_ok = first_verification.verdict is VerificationVerdict.PASS
        multi_ok = result.status is WorkflowStatus.COMPLETED and result.verification and result.verification.verdict is VerificationVerdict.PASS
        single_pass += single_ok; multi_pass += bool(multi_ok)
        revised = len(provider.generated) > 1; revision_attempts += revised; revision_successes += revised and bool(multi_ok)
        first_path = [event for event in result.trace if event.node not in {"verifier_agent", "synthesis_agent.revise"}]
        single_latency.append(sum(event.duration_ms for event in first_path))
        first_synthesis = next((event for event in result.trace if event.node == "synthesis_agent"), None)
        if first_synthesis and first_synthesis.usage:
            single_tokens += first_synthesis.usage.input_tokens + first_synthesis.usage.output_tokens
        multi_tokens += result.total_usage.input_tokens + result.total_usage.output_tokens
        details.append({"question_id": case["question_id"], "injected_fault": fault,
                        "single_agent_pass": single_ok, "multi_agent_pass": bool(multi_ok), "revised": revised})
    report = {
        "comparison_version": "step6-single-vs-multi-1.0.0", "provider": "deterministic_fake",
        "question_count": len(eligible), "single_agent_grounded_pass_rate": round(single_pass / len(eligible), 4),
        "multi_agent_grounded_pass_rate": round(multi_pass / len(eligible), 4),
        "revision_success_rate": round(revision_successes / max(1, revision_attempts), 4),
        "single_agent_average_latency_ms": round(sum(single_latency) / len(single_latency), 2),
        "multi_agent_average_latency_ms": round(sum(multi_latency) / len(multi_latency), 2),
        "single_agent_average_tokens": round(single_tokens / len(eligible), 2),
        "multi_agent_average_tokens": round(multi_tokens / len(eligible), 2),
        "single_agent_estimated_cost_per_query_usd": 0.0,
        "multi_agent_estimated_cost_per_query_usd": 0.0,
        "note": "This isolates deterministic verifier/revision value under seeded fake-provider faults; it is not a live-model quality claim.",
        "details": details,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__": main()
