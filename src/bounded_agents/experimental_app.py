"""Explicit development-only API integration. Never selected by the default app.

Application-owned factories, not request data, supply tools and providers. Each
query constructs a fresh single-use graph; B is an evaluation baseline only.
"""
from pathlib import Path

from src.api.app import create_app
from src.api.service import GraphService
from src.api.settings import AppSettings
from .diagnostic_policy import ARMS
from .models import AgentBudgetState
from .repair_targets import VERSION


def experimental_graph_factory(*, root, provider_factory, retriever_factory,
                               arm='C', fixture_mode=False):
    if arm not in ARMS:
        raise ValueError('Experimental arm must be B or C')
    selected_root=Path(root)
    def build():
        return ARMS[arm](selected_root, provider=provider_factory(),
            retriever=retriever_factory(), fixture_mode=fixture_mode,
            semantic_review_contract_version=VERSION,
            budgets=AgentBudgetState(max_total_calls=6,max_calls_per_role=6,max_retries=0),
            retrieval_method='dense', max_provider_attempts=1)
    return build


def create_experimental_app(*, settings: AppSettings, root, provider_factory,
                            retriever_factory, arm='C', fixture_mode=False):
    if settings.app_mode not in ('test','development') or settings.public_demo:
        raise ValueError('Experimental integration is development/test only')
    if fixture_mode and not settings.is_test:
        raise ValueError('Synthetic evidence is test-only')
    factory=experimental_graph_factory(root=root,provider_factory=provider_factory,
        retriever_factory=retriever_factory,arm=arm,fixture_mode=fixture_mode)
    service=GraphService(settings,request_scoped_graph_factory=factory)
    app=create_app(settings=settings,graph_service=service)
    app.state.experimental_arm=arm
    return app
