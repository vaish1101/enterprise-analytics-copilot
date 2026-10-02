from decimal import Decimal

import pytest

from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import ClaimType, SynthesisDraft, VerificationVerdict


@pytest.fixture(scope="module")
def baseline():
    graph = EnterpriseAnalyticsGraph()
    result = graph.run("What contributed to Henkel organic growth in H1 2026?", question_id="s6_v_base")
    state = graph.graph.get_state({"configurable": {"thread_id": "run_dummy"}}) if False else None
    return result


@pytest.mark.parametrize("fault", [
    "wrong_number", "wrong_unit", "wrong_period", "wrong_scope", "wrong_company",
    "wrong_metric", "provenance_relabel", "causal_overstatement", "missing_citation",
    "wrong_citation", "wrong_period_citation", "wrong_scope_citation",
    "henkel_rounding_caveat_omitted", "bridge_sign", "unsupported_interpretation",
    "calculated_without_lineage", "unsupported_mercedes_price",
])
def test_fault_injection_catalog_is_explicit(fault):
    # The executable evaluator maps every named fault to a concrete mutation/check.
    from scripts.evaluate_step6 import FAULT_TYPES
    assert fault in FAULT_TYPES


def test_decision_brief_has_complete_lineage():
    result = EnterpriseAnalyticsGraph().run(
        "How did Mercedes-Benz Cars adjusted EBIT change from Q2 2025 to Q2 2026?",
        question_id="s6_lineage",
    )
    assert result.verification.verdict is VerificationVerdict.PASS
    assert result.fact_ids
    assert result.calculation_run_ids
    assert result.total_usage.input_tokens > 0


def test_management_claim_is_not_causal():
    result = EnterpriseAnalyticsGraph().run(
        "What contributed to Mercedes-Benz Cars adjusted EBIT in Q2 2026?", question_id="s6_management"
    )
    management = [claim for claim in result.claims if claim.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED]
    assert management
    assert all("caused" not in claim.text.lower() for claim in management)

