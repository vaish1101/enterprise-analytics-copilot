"""Public-safe release tests: empty documentary store, no reports or paid calls."""
from pathlib import Path

import pytest

from scripts.public_release_check import findings, restricted
from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.persistence.checkpoint_store import CheckpointStore
from src.retrieval.retrieve import GovernedRetriever

ROOT = Path(__file__).resolve().parents[1]

class PoisonedProvider(DeterministicFakeProvider):
    def __init__(self, text, summary_only=False):
        super().__init__(); self.text = text; self.summary_only = summary_only

    def _draft(self, bundle, *, revision):
        draft = super()._draft(bundle, revision=revision)
        claims = draft.claims if self.summary_only else (draft.claims[0].model_copy(update={"text": self.text}),)
        return draft.model_copy(update={"claims": claims, "answer": self.text})

def graph(provider):
    return EnterpriseAnalyticsGraph(ROOT, provider=provider, retriever=GovernedRetriever([], root=ROOT), checkpoint_store=CheckpointStore(mode="memory"))

@pytest.mark.parametrize("text", [
    "Sales were EUR 999 million.", "Sales were EUR -10348 million.",
    "Sales were USD 10348 million.", "Sales were EUR 10,348 billion.",
    "Sales were 10348 EUR_million plus EUR 999 million.",
    "Sales were nine hundred ninety-nine million euros.",
])
def test_public_numerical_faults_fail_closed(text):
    result = graph(PoisonedProvider(text)).run("What were Henkel H1 2026 sales?", question_id="public_fault")
    assert result.verification.verdict.value != "PASS"
    assert not result.claims and text not in result.answer

def test_public_summary_does_not_escape_release():
    result = graph(PoisonedProvider("Sales were EUR 999 million.", summary_only=True)).run("What were Henkel H1 2026 sales?", question_id="public_summary")
    assert result.verification.verdict.value != "PASS"
    assert result.claims and "999" not in result.answer

def test_public_clean_numerical_release():
    result = graph(DeterministicFakeProvider()).run("What were Henkel H1 2026 sales?", question_id="public_clean")
    assert result.verification.verdict.value == "PASS"
    assert result.answer == " ".join(claim.text for claim in result.claims)
    assert "10348 EUR_million" in result.answer

@pytest.mark.parametrize("name", [".env", "data/raw_sources/report.pdf", "data/retrieval/local/index.json", "data/checkpoints/session.sqlite", "tmp/report.pdf", "model.safetensors"])
def test_restricted_publication_paths(name):
    assert restricted(name)

def test_secret_findings_never_return_matched_value():
    secret = "sk-" + "x" * 32
    result = findings("config/example.txt", secret.encode())
    assert result and secret not in repr(result)
    assert result[0]["category"] == "credential_prefix"

def test_env_template_is_empty_and_names_exist():
    source = "\n".join(path.read_text() for path in (ROOT / "src").rglob("*.py"))
    source += (ROOT / "Dockerfile").read_text() + (ROOT / "docker-compose.yml").read_text()
    for line in (ROOT / ".env.example").read_text().splitlines():
        if not line or line.startswith("#"): continue
        key, value = line.split("=", 1)
        assert not value and key in source
