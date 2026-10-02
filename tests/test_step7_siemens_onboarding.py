from pathlib import Path

from src.analytics.executor import AnalyticsExecutor
from src.analytics.facts import FactStore
from src.planning.models import PlanningStatus
from src.planning.planner import QuestionPlanner


ROOT = Path(__file__).resolve().parents[1]


def test_siemens_facts_are_owned_linked_and_isolated():
    facts = [record.fact for record in FactStore(ROOT).records if record.fact.company.value == "siemens"]
    assert len(facts) == 32
    assert all(fact.metric_id.value.startswith("siemens_") for fact in facts)
    assert all(fact.source_ids == ("siemens_q2_fy2026_earnings_release",) for fact in facts)
    assert not any(fact.metric_id.value.startswith(("henkel_", "mercedes_")) for fact in facts)


def test_siemens_planning_and_analytics_use_generic_paths():
    planner = QuestionPlanner(ROOT); executor = AnalyticsExecutor(ROOT)
    plan = planner.plan("How did Siemens revenue change from Q2 2025 to Q2 2026?")
    assert plan.status is PlanningStatus.READY
    result = executor.execute(plan)
    assert result.primary_result.value == 19756
    assert result.absolute_change == -1


def test_siemens_mobility_overlap_generic_fix():
    plan = QuestionPlanner(ROOT).plan("What was Siemens Mobility segment profit margin in Q2 2026?")
    assert plan.status is PlanningStatus.READY
    assert plan.primary_target.business_scope == "siemens_mobility"


def test_no_siemens_specific_prompt_graph_or_verifier_logic():
    paths = [*sorted((ROOT / "prompts").glob("*.md")), ROOT / "src/orchestration/graph.py", ROOT / "src/orchestration/verifier.py"]
    assert all("siemens" not in path.read_text(encoding="utf-8").lower() for path in paths)
