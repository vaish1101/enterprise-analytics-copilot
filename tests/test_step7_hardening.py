from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.analytics.executor import AnalyticsExecutor
from src.evaluation.contradiction_detector import ContradictionDetector
from src.evaluation.run_manifest import build_run_manifest
from src.llm.base import ProviderConfigurationError, ProviderRefusalError, ProviderRetryableError
from src.llm.fake_provider import DeterministicFakeProvider
from src.llm.openai_provider import OpenAIStructuredProvider
from src.llm.provider import provider_from_environment
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import WorkflowStatus
from src.persistence.checkpoint_store import CheckpointStore, redact_dsn
from src.planning.models import CompanyId, MetricId, PeriodId, PlanTarget
from src.planning.planner import QuestionPlanner
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import GovernedRetriever


ROOT = Path(__file__).resolve().parents[1]


def _retrieval_result():
    units = [EvidenceUnit.model_validate_json(line) for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text().splitlines() if line]
    return GovernedRetriever(units, root=ROOT).retrieve(
        __import__("src.retrieval.query", fromlist=["query_from_plan"]).query_from_plan(
            QuestionPlanner(ROOT).plan("What were Henkel H1 2026 sales?", question_id="conflict")
        ), method="dense"
    ).results[0]


def _analytics():
    plan = QuestionPlanner(ROOT).plan("What were Henkel H1 2026 sales?", question_id="conflict")
    return AnalyticsExecutor(ROOT).execute(plan)


def test_extensible_identifiers_are_catalog_ready():
    company = CompanyId("unseen_enterprise")
    target = PlanTarget(company=company, metric_id=MetricId("unseen_enterprise_revenue"))
    assert target.company.value == "unseen_enterprise"
    assert PeriodId("Q3_2030").value == "Q3_2030"


@pytest.mark.parametrize("text,period,scope,metric,expected", [
    ("Revenue was €10,348 million.", "H1_2026", "henkel_group", "henkel_sales", 0),
    ("Revenue was €10,348.4 million.", "H1_2026", "henkel_group", "henkel_sales", 0),
    ("Revenue was €10,349 million.", "H1_2026", "henkel_group", "henkel_sales", 1),
    ("Revenue was €10,349 million.", "H1_2025", "henkel_group", "henkel_sales", 0),
    ("Revenue was €10,349 million.", "H1_2026", "henkel_other", "henkel_sales", 0),
    ("Revenue was €10,349 million.", "H1_2026", "henkel_group", "henkel_organic_sales_growth", 0),
    ("Revenue was 10,348%.", "H1_2026", "henkel_group", "henkel_sales", 1),
])
def test_contradiction_detector_is_conservative(text, period, scope, metric, expected):
    item = _retrieval_result().model_copy(update={
        "text": text, "reporting_periods": (period,), "business_scopes": (scope,), "metric_ids": (metric,),
    })
    conflicts = ContradictionDetector().detect(_analytics(), (item,))
    assert len(conflicts) == expected


def test_provider_environment_requires_explicit_configuration(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(ProviderConfigurationError): provider_from_environment()
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        provider_from_environment()
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    assert isinstance(provider_from_environment(allow_fake=True), DeterministicFakeProvider)


def test_openai_provider_extracts_real_usage_and_configured_cost(monkeypatch):
    class Output(BaseModel):
        answer: str

    class Responses:
        @staticmethod
        def parse(**kwargs):
            assert kwargs["text_format"] is Output
            return SimpleNamespace(
                output_parsed=Output(answer="governed"), output=(),
                usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-logged")
    provider = OpenAIStructuredProvider(
        model="test-model", input_cost_per_million=Decimal("2"),
        output_cost_per_million=Decimal("8"),
    )
    provider.client = SimpleNamespace(responses=Responses())
    result = provider.generate_structured(
        role="synthesis", prompt="test", payload={}, output_model=Output,
        prompt_version="test-v1",
    )
    assert result.usage.input_tokens == 1000
    assert result.usage.output_tokens == 500
    assert result.usage.estimated_cost_usd == Decimal("0.006")


def test_openai_provider_uses_decimal_safe_wire_schema(monkeypatch):
    from src.orchestration.models import SynthesisDraft

    class Responses:
        @staticmethod
        def parse(**kwargs):
            wire = kwargs["text_format"]
            assert wire is not SynthesisDraft
            parsed = wire.model_validate({
                "draft_id": "draft_wire", "question_id": "wire", "answer": "Revenue was 1.25.",
                "claims": [{
                    "claim_id": "claim_001", "claim_type": "REPORTED", "text": "Revenue was 1.25.",
                    "company_id": "henkel", "metric_id": "henkel_sales", "business_scope": "henkel_group",
                    "periods": ["H1_2026"], "value": "1.25", "unit": "EUR_million", "fact_ids": [1],
                    "calculation_run_ids": [], "evidence_ids": [],
                }], "limitations": [], "revision_number": 0,
            })
            return SimpleNamespace(
                output_parsed=parsed, output=(),
                usage=SimpleNamespace(input_tokens=10, output_tokens=10),
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-logged")
    provider = OpenAIStructuredProvider(model="test-model")
    provider.client = SimpleNamespace(responses=Responses())
    result = provider.generate_structured(
        role="synthesis", prompt="test", payload={}, output_model=SynthesisDraft,
        prompt_version="test-v1",
    )
    assert result.value.claims[0].value == Decimal("1.25")


def test_openai_provider_removes_invalid_claims_and_rebuilds_answer(monkeypatch):
    from src.orchestration.models import SynthesisDraft

    class Responses:
        @staticmethod
        def parse(**kwargs):
            wire = kwargs["text_format"]
            claims = [
                {
                    "claim_id": "claim_001", "claim_type": "REPORTED",
                    "text": "Mercedes-Benz Cars adjusted EBIT was 909 EUR million.",
                    "company_id": "mercedes_benz_group", "metric_id": "mercedes_adjusted_ebit",
                    "business_scope": "mercedes_cars", "periods": ["Q2_2026"],
                    "value": "909", "unit": "EUR_million", "fact_ids": [110],
                    "calculation_run_ids": [], "evidence_ids": ["evidence_0110"],
                },
                {
                    "claim_id": "claim_002", "claim_type": "MANAGEMENT_ATTRIBUTED",
                    "text": "Volume / structure / net pricing contributed -602 EUR million.",
                    "company_id": "mercedes_benz_group",
                    "metric_id": "mercedes_bridge_volume_structure_net_pricing",
                    "business_scope": "mercedes_cars", "periods": ["Q2_2026"],
                    "value": "-602", "unit": "EUR_million", "fact_ids": [141],
                    "calculation_run_ids": [], "evidence_ids": ["evidence_0141"],
                },
                {
                    "claim_id": "claim_003", "claim_type": "REPORTED",
                    "text": "Invalid multi-value claim must not survive.",
                    "company_id": "mercedes_benz_group", "metric_id": "mercedes_adjusted_ebit",
                    "business_scope": "mercedes_cars", "periods": ["Q2_2026"],
                    "value": "909; 1228; -26.0", "unit": "EUR_million", "fact_ids": [110],
                    "calculation_run_ids": [], "evidence_ids": [],
                },
                {
                    "claim_id": "claim_004", "claim_type": "CALCULATED",
                    "text": "Invalid calculated claim must not survive.",
                    "company_id": "mercedes_benz_group", "metric_id": "mercedes_adjusted_ebit",
                    "business_scope": "mercedes_cars", "periods": ["Q2_2026"],
                    "value": "-319", "unit": "EUR_million", "fact_ids": [109, 110],
                    "calculation_run_ids": [], "evidence_ids": [],
                },
            ]
            parsed = wire.model_validate({
                "draft_id": "draft_decomposition", "question_id": "step86b",
                "answer": "Original answer containing invalid claims.", "claims": claims,
                "limitations": [], "revision_number": 0,
            })
            return SimpleNamespace(
                output_parsed=parsed, output=(),
                usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-logged")
    provider = OpenAIStructuredProvider(model="test-model")
    provider.client = SimpleNamespace(responses=Responses())
    result = provider.generate_structured(
        role="synthesis", prompt="test", payload={}, output_model=SynthesisDraft,
        prompt_version="test-v1",
    )

    assert [claim.value for claim in result.value.claims] == [Decimal("909"), Decimal("-602")]
    assert "Volume / structure / net pricing" in result.value.answer
    assert "price alone" not in result.value.answer.lower()
    assert "Invalid" not in result.value.answer
    assert result.value.answer == " ".join(claim.text for claim in result.value.claims)
    assert "2 malformed provider claim(s)" in result.value.limitations[-1]


def test_non_retryable_provider_refusal_is_not_retried():
    class Refusing(DeterministicFakeProvider):
        def __init__(self): super().__init__(); self.calls = 0
        def generate_structured(self, **kwargs): self.calls += 1; raise ProviderRefusalError("refused")
    provider = Refusing()
    result = EnterpriseAnalyticsGraph(ROOT, provider=provider).run("What were Henkel H1 2026 sales?", question_id="refuse_once")
    assert result.status is WorkflowStatus.REFUSED
    assert provider.calls == 1


def test_retryable_provider_error_is_bounded_and_recovers():
    class Flaky(DeterministicFakeProvider):
        def __init__(self): super().__init__(); self.calls = 0
        def generate_structured(self, **kwargs):
            self.calls += 1
            if self.calls == 1: raise ProviderRetryableError("transient")
            return super().generate_structured(**kwargs)
    provider = Flaky()
    result = EnterpriseAnalyticsGraph(ROOT, provider=provider).run("What were Henkel H1 2026 sales?", question_id="retry_once")
    assert result.status is WorkflowStatus.COMPLETED
    assert provider.calls == 2


def test_sqlite_checkpoint_persists_across_graph_instances(tmp_path):
    path = tmp_path / "state.sqlite"
    store1 = CheckpointStore(mode="sqlite", uri=str(path))
    graph1 = EnterpriseAnalyticsGraph(ROOT, checkpoint_store=store1)
    first = graph1.run("What were Henkel H1 2026 sales?", question_id="persist", thread_id="persist-thread")
    store1.close()
    store2 = CheckpointStore(mode="sqlite", uri=str(path))
    graph2 = EnterpriseAnalyticsGraph(ROOT, checkpoint_store=store2)
    second = graph2.run("What were Henkel H1 2026 sales?", question_id="persist", thread_id="persist-thread")
    store2.close()
    assert second.run_id == first.run_id
    assert second.trace == first.trace


def test_dsn_and_manifest_are_secret_free(monkeypatch):
    assert redact_dsn("postgresql://alice:secret@localhost/db") == "postgresql://alice:***@localhost/db"
    monkeypatch.setenv("OPENAI_API_KEY", "never-write-this")
    manifest = build_run_manifest(
        ROOT, run_id="manifest-test", provider="openai", model="test-model",
        model_settings={"temperature": 0}, core_freeze_hash="a" * 64,
        evaluation_dataset=ROOT / "evals/step6_dev.jsonl",
    )
    assert "never-write-this" not in manifest.model_dump_json()
    assert len(manifest.prompt_fingerprints) == 5
    assert all(len(item.sha256) == 64 for item in manifest.prompt_fingerprints)
