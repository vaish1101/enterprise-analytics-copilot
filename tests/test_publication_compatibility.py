"""Public API compatibility and isolated opt-in responses; entirely scripted."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from src.api import schemas
from src.api.app import create_app
from src.api.service import GraphService
from src.api.sessions import SessionStore
from src.api.settings import AppSettings

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', ['final_release_status.md', 'release_candidate_architecture.md',
    'release_candidate_demo.md', 'release_candidate_evaluation.md'])
def test_curated_release_docs_are_allowed_without_allowing_private_artifacts(name):
    from scripts.public_release_check import category
    assert category('docs/' + name)[0] == 'KEEP PUBLIC'
    assert category('docs/unreviewed_internal_report.md')[0] == 'MOVE / CURATE'
    assert category('.publication-private/report.md')[0] == 'PRIVATE / DO NOT PUBLISH'

@pytest.mark.parametrize('name,fields', [
    ('AnalyticsFact', 'fact_id company_id metric_id label business_scope period period_grain value unit provenance bridge_role component_order'),
    ('AnalyticsChange', 'kind value unit calculation_run_id'),
    ('RankedComponentResponse', 'rank fact_id metric_id label value unit provenance'),
    ('ReconciliationResponse', 'rule_id expected_value calculated_value absolute_difference tolerance passed source_fact_ids calculation_run_id'),
    ('AnalyticsResponse', 'operation primary comparison changes components supporting ranked reconciliations calculation_run_ids warnings limitations'),
    ('FactSourceResponse', 'fact_id source_id source_title official_url source_type location page_or_sheet cell_or_range evidence_type'),
    ('ClarificationOption', 'label detail question'),
    ('GovernedAlternative', 'label question'),
    ('MetricLabel', 'label reported_name unit company_id'),
    ('ScopeLabel', 'label company_id scope_type'),
    ('PeriodLabel', 'company_id period_id period_grain label fiscal'),
    ('CatalogLabels', 'metrics scopes periods'),
])
def test_existing_presentation_types_are_preserved(name, fields):
    assert set(getattr(schemas, name).model_fields) == set(fields.split())


def settings():
    return AppSettings(app_mode='demo', public_demo=True, checkpoint_backend='memory', session_db_path='')


def test_default_factory_and_two_value_helper_are_preserved():
    service = GraphService(settings(), session_store=SessionStore(None))
    assert service.request_scoped_graph_factory is None
    result, evidence = service._run_locked('What were Henkel H1 2026 sales?', 'compatibility', 'compatibility')
    assert result.status.value == 'COMPLETED' and evidence.analytics.primary_result.value == 10348
    assert service.graph.__class__.__name__ == 'EnterpriseAnalyticsGraph'


def test_default_api_preserves_metadata_and_structured_numbers():
    with TestClient(create_app(settings=settings())) as api:
        metadata = api.get('/api/v1/metadata').json()
        assert metadata['labels']['metrics'] and metadata['labels']['scopes']
        assert metadata['provider_mode'] == 'test'
        result = api.post('/api/v1/query', json={'question': 'What were Henkel H1 2026 sales?'}).json()
        assert result['analytics']['primary']['value'] == '10348'
        assert result['fact_sources'][0]['official_url'].startswith('https://')
        assert result['product'] is None and isinstance(result['execution']['provider_calls'], int)
        assert result['clarification_options'] == [] and result['alternatives'] == []
        refused = api.post('/api/v1/query', json={'question': 'What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?'}).json()
        assert refused['status'] == 'REFUSED' and not refused['claims']
        assert refused['analytics'] is None and refused['fact_sources'] == []
        assert refused['verification'] is None or refused['verification']['verdict'] != 'PASS'


@pytest.mark.parametrize('arm', ['B', 'C'])
@pytest.mark.parametrize('profile,question,mode', [
    ('normal', 'Describe the definition of Henkel organic sales growth.', 'FULL'),
    ('normal', 'What drove Mercedes-Benz Vans adjusted EBIT in Q2 2026?', 'PARTIAL'),
    ('empty', 'Describe the definition of Henkel organic sales growth.', 'WITHHELD'),
    ('normal', 'Isolate only price in Mercedes-Benz Cars adjusted EBIT in Q2 2026.', 'WITHHELD'),
])
def test_opt_in_release_projection_and_legacy_fields_coexist(arm, profile, question, mode):
    from src.bounded_agents.experimental_app import create_experimental_app
    from src.bounded_agents.comparison_fixtures import ScenarioProvider, ScriptedRankingRetriever
    app = create_experimental_app(settings=AppSettings(app_mode='test', checkpoint_backend='memory', session_db_path=''),
        root=ROOT, provider_factory=lambda: ScenarioProvider('normal'),
        retriever_factory=lambda: ScriptedRankingRetriever(profile, ROOT), arm=arm, fixture_mode=True)
    with TestClient(app) as api:
        response = api.post('/api/v1/query', json={'question': question})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['product']['release_mode'] == mode
        assert {'analytics', 'fact_sources', 'clarification_options', 'alternatives'} <= data.keys()
        assert data['product']['released_claim_ids'] == [c['claim_id'] for c in data['claims']]
        if mode in {'FULL', 'PARTIAL'}:
            assert data['verification']['verdict'] == 'PASS'
        else:
            assert not data['claims'] and data['analytics'] is None and data['fact_sources'] == []
        if mode == 'PARTIAL':
            assert data['product']['withheld_components']
            assert all(c['value'] is not None for c in data['claims'])
        assert app.state.graph_service.request_scoped_graph_factory is not None


def test_experimental_projection_cannot_be_selected_by_request_or_production():
    from src.bounded_agents.experimental_app import create_experimental_app
    with pytest.raises(ValueError):
        create_experimental_app(settings=AppSettings(app_mode='production'), root=ROOT,
            provider_factory=lambda: None, retriever_factory=lambda: None)
    with TestClient(create_app(settings=settings())) as api:
        response = api.post('/api/v1/query', json={'question': 'What were Henkel H1 2026 sales?', 'arm': 'C'})
        assert response.status_code == 422
