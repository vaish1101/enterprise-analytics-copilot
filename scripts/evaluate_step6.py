"""Reproducible Step 6 routing, grounding, verification and fault evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import Claim, ClaimType, SynthesisDraft, VerificationVerdict, WorkflowStatus
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import build_default_retriever


FAULT_TYPES = (
    "wrong_number", "wrong_unit", "wrong_period", "wrong_scope", "wrong_company",
    "wrong_metric", "unsupported_mercedes_price", "provenance_relabel",
    "causal_overstatement", "missing_citation", "wrong_citation",
    "wrong_period_citation", "wrong_scope_citation", "henkel_rounding_caveat_omitted",
    "bridge_sign", "unsupported_interpretation", "calculated_without_lineage",
)


def _cases(split: str) -> list[dict]:
    path = ROOT / f"evals/step6_{split}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _percentile(values: list[float], fraction: float) -> float:
    if not values: return 0.0
    ordered = sorted(values); index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
    return ordered[index]


def evaluate(cases: list[dict], graph: EnterpriseAnalyticsGraph) -> tuple[dict, list[dict]]:
    counts = {key: 0 for key in (
        "route", "status", "tool_selection", "verifier", "grounded", "numeric", "citation", "provenance", "causality", "clarification", "refusal"
    )}
    denominators = {key: 0 for key in counts}
    failures = []; latencies = []; input_tokens = output_tokens = 0; total_cost = 0.0
    for case in cases:
        started = time.perf_counter()
        result = graph.run(case["question"], question_id=case["question_id"])
        latencies.append((time.perf_counter() - started) * 1000)
        counts["route"] += result.route.value == case["expected_route"]; denominators["route"] += 1
        counts["status"] += result.status.value == case["expected_status"]; denominators["status"] += 1
        expected_nodes = {
            "ANALYTICS_ONLY": {"analytics_agent"}, "KNOWLEDGE_ONLY": {"knowledge_agent"},
            "HYBRID": {"analytics_agent", "knowledge_agent"},
            "DECOMPOSITION_EXPLANATION": {"analytics_agent", "knowledge_agent"},
            "NEEDS_CLARIFICATION": set(), "UNSUPPORTED": set(),
        }[case["expected_route"]]
        actual_nodes = {event.node for event in result.trace if event.node in {"analytics_agent", "knowledge_agent"}}
        denominators["tool_selection"] += 1; counts["tool_selection"] += actual_nodes == expected_nodes
        if result.verification:
            denominators["verifier"] += 1; counts["verifier"] += result.verification.verdict is VerificationVerdict.PASS
            denominators["grounded"] += 1; counts["grounded"] += all(c.support.value == "SUPPORTED" for c in result.verification.claim_checks)
            numeric_claims = [c for c in result.claims if c.value is not None]
            denominators["numeric"] += bool(numeric_claims); counts["numeric"] += bool(numeric_claims) and all(c.fact_ids or c.calculation_run_ids for c in numeric_claims)
            doc_ids = {eid for c in result.claims for eid in c.evidence_ids if eid.startswith("eu_")}
            denominators["citation"] += bool(doc_ids); counts["citation"] += bool(doc_ids) and doc_ids.issubset(result.evidence_ids)
            denominators["provenance"] += 1; counts["provenance"] += all(c.claim_type is not ClaimType.CALCULATED or c.calculation_run_ids for c in result.claims)
            denominators["causality"] += 1; counts["causality"] += all("caused" not in c.text.lower() for c in result.claims if c.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED)
        if result.route.value == "NEEDS_CLARIFICATION":
            denominators["clarification"] += 1; counts["clarification"] += result.status is WorkflowStatus.NEEDS_CLARIFICATION
        if result.route.value == "UNSUPPORTED":
            denominators["refusal"] += 1; counts["refusal"] += result.status is WorkflowStatus.REFUSED
        input_tokens += result.total_usage.input_tokens; output_tokens += result.total_usage.output_tokens
        total_cost += float(result.total_usage.estimated_cost_usd)
        if result.route.value != case["expected_route"] or result.status.value != case["expected_status"]:
            failures.append({"question_id": case["question_id"], "expected": case, "actual_route": result.route.value, "actual_status": result.status.value})
    metrics = {f"{key}_accuracy": round(counts[key] / max(1, denominators[key]), 4) for key in counts}
    metrics.update({
        "question_count": len(cases), "latency_p50_ms": round(statistics.median(latencies), 2),
        "latency_p95_ms": round(_percentile(latencies, .95), 2), "input_tokens": input_tokens,
        "output_tokens": output_tokens, "estimated_cost_usd": round(total_cost, 6),
        "average_tokens_per_query": round((input_tokens + output_tokens) / max(1, len(cases)), 2),
        "estimated_cost_per_query_usd": round(total_cost / max(1, len(cases)), 6),
        "unsupported_claim_rate": round(1 - counts["grounded"] / max(1, denominators["grounded"]), 4),
        "causality_violation_rate": round(1 - counts["causality"] / max(1, denominators["causality"]), 4),
    })
    return metrics, failures


def fault_injection() -> dict:
    detected: dict[str, bool] = {}
    common = {"wrong_number", "wrong_unit", "wrong_period", "wrong_scope", "wrong_company", "wrong_metric", "provenance_relabel", "calculated_without_lineage"}
    for fault in common:
        qid = f"fault_{fault}"
        provider = DeterministicFakeProvider({qid: fault})
        result = EnterpriseAnalyticsGraph(ROOT, provider=provider).run("What were Henkel H1 2026 sales?", question_id=qid)
        detected[fault] = len([e for e in result.trace if e.node == "verifier_agent"]) == 2
    qid = "fault_causal_overstatement"
    result = EnterpriseAnalyticsGraph(ROOT, provider=DeterministicFakeProvider({qid: "causal_overstatement"})).run(
        "What contributed to Mercedes-Benz Cars adjusted EBIT in Q2 2026?", question_id=qid)
    detected["causal_overstatement"] = len([e for e in result.trace if e.node == "verifier_agent"]) == 2
    qid = "fault_wrong_citation"
    result = EnterpriseAnalyticsGraph(ROOT, provider=DeterministicFakeProvider({qid: "wrong_citation"})).run(
        "How does Henkel define organic sales growth?", question_id=qid)
    detected["wrong_citation"] = len([e for e in result.trace if e.node == "verifier_agent"]) == 2
    detected["missing_citation"] = _manual_document_fault("missing_citation")
    detected["wrong_period_citation"] = _manual_document_fault("wrong_period_citation")
    detected["wrong_scope_citation"] = _manual_document_fault("wrong_scope_citation")
    detected["unsupported_interpretation"] = _manual_document_fault("unsupported_interpretation")
    detected["bridge_sign"] = _manual_numeric_fault("bridge_sign")
    detected["henkel_rounding_caveat_omitted"] = _rounding_fault()
    unsupported = EnterpriseAnalyticsGraph(ROOT).run(
        "How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?", question_id="fault_unsupported_price")
    detected["unsupported_mercedes_price"] = unsupported.status is WorkflowStatus.REFUSED
    return {"fault_count": len(FAULT_TYPES), "detected_count": sum(detected.values()),
            "detection_rate": round(sum(detected.values()) / len(FAULT_TYPES), 4), "detected": detected}


def _clean_state(question: str, qid: str):
    provider = DeterministicFakeProvider(); graph = EnterpriseAnalyticsGraph(ROOT, provider=provider)
    graph.run(question, question_id=qid)
    return graph, graph.last_state["evidence"], provider.generated[0]


def _manual_document_fault(kind: str) -> bool:
    graph, evidence, draft = _clean_state("How does Henkel define organic sales growth?", f"manual_{kind}")
    claim = draft.claims[0]
    if kind == "missing_citation": claim = claim.model_copy(update={"evidence_ids": ()})
    elif kind == "wrong_period_citation": claim = claim.model_copy(update={"periods": ("Q1_1999",)})
    elif kind == "wrong_scope_citation": claim = claim.model_copy(update={"business_scope": "wrong_scope"})
    else: claim = claim.model_copy(update={"claim_type": ClaimType.INTERPRETATION, "evidence_ids": ()})
    broken = draft.model_copy(update={"claims": (claim,)})
    return graph.verifier.verify(broken, evidence).verdict is not VerificationVerdict.PASS


def _manual_numeric_fault(kind: str) -> bool:
    graph, evidence, draft = _clean_state("What contributed to Mercedes-Benz Cars adjusted EBIT in Q2 2026?", "manual_bridge")
    index = next(i for i,c in enumerate(draft.claims) if c.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED)
    claims = list(draft.claims); claim = claims[index]
    claims[index] = claim.model_copy(update={"value": -claim.value})
    return graph.verifier.verify(draft.model_copy(update={"claims": tuple(claims)}), evidence).verdict is not VerificationVerdict.PASS


def _rounding_fault() -> bool:
    graph, evidence, draft = _clean_state("Reconcile Henkel Adhesive Technologies organic growth in H1 2026.", "manual_rounding")
    if not evidence.analytics or not evidence.analytics.warnings:
        return False
    broken = draft.model_copy(update={"limitations": (), "answer": draft.answer.replace("rounding", "")})
    return graph.verifier.verify(broken, evidence).verdict is not VerificationVerdict.PASS


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--semantic", action="store_true"); parser.add_argument("--output")
    args = parser.parse_args()
    retriever = None
    if args.semantic:
        units = [EvidenceUnit.model_validate_json(line) for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text().splitlines() if line]
        retriever = build_default_retriever(units, root=ROOT)
    graph = EnterpriseAnalyticsGraph(ROOT, retriever=retriever)
    metrics, failures = evaluate(_cases(args.split), graph)
    report = {"evaluation_version": "step6-eval-1.0.0", "split": args.split,
              "provider": graph.provider.name, "retrieval_model": graph.knowledge_tool.retriever.vector.provider.model_name,
              "metrics": metrics, "failures": failures}
    if args.split == "dev": report["fault_injection"] = fault_injection()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__": main()
