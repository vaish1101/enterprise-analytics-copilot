"""Credential-free spike harness. Synthetic evidence; no held-set access/writes."""
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import (AnalyticsAction, AnalyticsInvestigationRequest,
    AnalyticsFollowUpDecision, EvidenceSearchStrategy, EvidenceSearchRequest,
    EvidenceFollowUpDecision, EvidenceCoverageAssessment, CriticFeedback,
    CriticDecision, CriticIssue)
from src.bounded_agents.runtime import BoundedAgentsGraph
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.embeddings import LocalHashEmbeddingProvider


def synthetic_units():
    """Not issuer quotations: wholly artificial text owned by this dev harness."""
    rows = [
        ("henkel", "henkel_organic_sales_growth", "henkel_group", (), "METRIC_DEFINITION", "DEFINITION"),
        ("henkel", "henkel_sales", "henkel_group", ("H1_2026",), "NARRATIVE_SECTION", "COMMENTARY"),
        ("mercedes_benz_group", "mercedes_adjusted_ebit", "mercedes_cars", ("Q2_2026", "Q2_2025"), "BRIDGE_DECOMPOSITION", "MANAGEMENT_ATTRIBUTED"),
    ]
    units = []
    for index, (company, metric, scope, periods, kind, relevance) in enumerate(rows):
        text = "Synthetic development fixture, not an issuer quotation. Governed definition and reporting context. Management attribution is not causal identification; combined categories remain unsplit."
        units.append(EvidenceUnit.model_validate({
            "evidence_unit_id": "eu_" + hashlib.sha256(str(index).encode()).hexdigest()[:24],
            "source_id": f"synthetic_dev_{index}", "company_id": company,
            "source_title": "Synthetic development evidence", "source_type": "development_fixture",
            "reporting_periods": periods, "publication_date": "2026-10-01", "page_number": 1,
            "printed_page_or_slide": "1", "section": "Synthetic governed context",
            "business_scopes": (scope,), "metric_ids": (metric,), "evidence_unit_type": kind,
            "evidence_relevance": relevance, "source_hierarchy": "PRIMARY",
            "evidence_method": "DOCUMENT_TEXT", "text": text,
            "official_url": "https://example.invalid/synthetic-development-fixture",
            "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "parser_version": "synthetic-dev-1", "chunking_version": "synthetic-dev-1"}, strict=False))
    return units


class ScenarioProvider(SpikeFixtureProvider):
    def __init__(self, case):
        self.case = case
        fixtures = {}
        if "initial" in case:
            fixtures["analytics.choose"] = AnalyticsInvestigationRequest(action=case["initial"])
        if "follow_up" in case:
            fixtures["analytics.follow_up"] = AnalyticsFollowUpDecision(action=case["follow_up"])
        if "search" in case:
            fixtures["evidence.choose"] = EvidenceSearchRequest(strategy=case["search"])
        if "search_follow_up" in case:
            fixtures["evidence.coverage"] = EvidenceFollowUpDecision(
                coverage=EvidenceCoverageAssessment(sufficient=False, selected_evidence_ids=()),
                follow_up=case["search_follow_up"])
        if "critic" in case:
            objection = CriticFeedback(decision=CriticDecision.REJECT if case.get("reject") else CriticDecision.REVISE,
                issues=(CriticIssue(case["critic"]),), claim_ids=(), evidence_sufficient=True)
            approve = CriticFeedback(decision=CriticDecision.APPROVE, issues=(), claim_ids=(), evidence_sufficient=True)
            fixtures["critic"] = [objection, approve]
        super().__init__(fixtures=fixtures)

    def _draft(self, bundle, *, revision):
        draft = super()._draft(bundle, revision=revision)
        if not revision and self.case.get("critic") == "causal_overclaim":
            claim = draft.claims[0].model_copy(update={"text": draft.claims[0].text + " This proves a causal effect."})
            draft = draft.model_copy(update={"claims": (claim, *draft.claims[1:]), "answer": " ".join(x.text for x in (claim, *draft.claims[1:]))})
        if not revision and self.case.get("critic") == "missing_limitation":
            draft = draft.model_copy(update={"limitations": ()})
        return draft


def evaluate():
    cases = json.loads((ROOT / "config/bounded_agents_dev.json").read_text())["cases"]
    rows = []
    for case in cases:
        provider = ScenarioProvider(case)
        retriever = GovernedRetriever([] if case.get("empty_corpus") else synthetic_units(),
            root=ROOT, embedding_provider=LocalHashEmbeddingProvider())
        graph = BoundedAgentsGraph(ROOT, provider=provider, retriever=retriever)
        started = time.monotonic()
        brief = graph.run(case["question"], question_id=case["id"])
        events = graph.agent_trace
        rows.append({"id": case["id"], "status": brief.status.value,
            "expected": case["expected"], "task_completed_as_expected": brief.status.value == case["expected"],
            "chosen_actions": [x.action.value for x in graph.observations],
            "search_strategies": [x.action for x in events if x.role == "evidence" and x.tool_requested],
            "follow_ups": sum(x.follow_up_requested for x in events if x.tool_requested),
            "critic_outcomes": [x.critic_outcome.value for x in events if x.critic_outcome],
            "verifier_outcomes": [x.verifier_outcome for x in events if x.verifier_outcome],
            "model_calls": graph.budget.calls, "fixture_tokens": graph.budget.tokens,
            "latency_ms": round((time.monotonic()-started)*1000, 2),
            "reconciliation": [x.passed for obs in graph.observations for x in obs.result.reconciliation_results],
            "fallback": False, "real_model_useful_decision": None,
            "real_model_critic_useful_intervention": None,
            "real_model_critic_false_positive": None,
            "unnecessary_follow_up": None})
    return {"mode": "bounded_agents_v2", "provider": "deterministic_fake",
        "evidence": "synthetic development fixtures, not publisher passages",
        "evaluated_at": datetime.now(UTC).isoformat(), "cases": rows,
        "completion": {"passed": sum(x["task_completed_as_expected"] for x in rows), "total": len(rows)},
        "agentic_value": "NOT MEASURED: scripted choices cannot demonstrate live model agency",
        "live_cost_latency": "NOT MEASURED", "recommendation": "MODIFY"}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
