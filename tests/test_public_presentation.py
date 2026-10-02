"""Public-safe presentation adapter regressions; no changes to numerical authority."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from src.api.catalog import ProductCatalog
from src.api.presentation import governed_numbers
from src.api.service import GraphService
from src.api.sessions import SessionStore
from src.api.settings import AppSettings
from src.orchestration.models import WorkflowStatus

ROOT = Path(__file__).resolve().parents[1]

def service():
    return GraphService(AppSettings(app_mode='demo', public_demo=True, checkpoint_backend='memory', session_db_path=''), session_store=SessionStore(None))

def test_public_exact_fact_and_source_are_serialized():
    result = asyncio.run(service().query('What were Henkel H1 2026 sales?', 'presentation_fact', None))
    assert result.status == 'COMPLETED'
    assert result.analytics.primary.value == result.claims[0].value == '10348'
    assert result.fact_sources[0].fact_id == result.claims[0].fact_ids[0]
    assert result.fact_sources[0].official_url.startswith('https://')
    assert set(result.fact_sources[0].model_dump()) == {'fact_id', 'source_id', 'source_title', 'official_url', 'source_type', 'location', 'page_or_sheet', 'cell_or_range', 'evidence_type'}

def test_public_comparison_reuses_calculation_values():
    result = asyncio.run(service().query('Calculate the difference between Henkel H1 2025 sales and H1 2026 sales.', 'presentation_comparison', None))
    assert result.analytics.primary.value == '10348'
    assert result.analytics.comparison.value == '10402'
    assert next(c for c in result.analytics.changes if c.kind == 'absolute').value == '-54'
    runs = {r for claim in result.claims for r in claim.calculation_run_ids}
    assert set(result.analytics.calculation_run_ids) <= runs

def test_refusal_never_exposes_checked_but_unreleased_figures():
    result = asyncio.run(service().query('What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?', 'presentation_refused', None))
    assert result.status == 'REFUSED' and not result.claims
    assert result.analytics is None and result.fact_sources == []
    assert result.verification is None or result.verification.verdict != 'PASS'

def test_partial_release_does_not_serialize_withheld_facts():
    instance = service()
    result, evidence = instance._run_locked('How did Henkel sales change from H1 2025 to H1 2026?', 'partial_source', 'partial_source')
    first = SimpleNamespace(fact_ids=(evidence.analytics.primary_result.fact_id,), calculation_run_ids=())
    analytics, sources = governed_numbers(result, evidence, [first], ProductCatalog(ROOT))
    assert analytics is None and len(sources) == 1
    withheld = SimpleNamespace(status=WorkflowStatus.REFUSED)
    assert governed_numbers(withheld, evidence, [first], ProductCatalog(ROOT)) == (None, [])
