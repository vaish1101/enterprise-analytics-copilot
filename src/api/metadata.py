from __future__ import annotations

from .schemas import CompanyMetadata, ExampleGroup, MetadataResponse
from .settings import AppSettings
from .settings import ROOT
from .catalog import product_catalog


def product_metadata(settings: AppSettings) -> MetadataResponse:
    return MetadataResponse(
        system_version=settings.system_version,
        headline="Governed AI for KPI analysis, variance explanation, document context, and decision support",
        companies=[
            CompanyMetadata(id="henkel", name="Henkel", periods=["H1 2026", "H1 2025", "Q2 2026", "Q2 2025"], scopes=["Group", "Adhesive Technologies", "Consumer Brands"]),
            CompanyMetadata(id="mercedes_benz_group", name="Mercedes-Benz", periods=["H1 2026", "H1 2025", "Q2 2026", "Q2 2025"], scopes=["Group", "Cars", "Vans", "Mobility"]),
            CompanyMetadata(id="siemens", name="Siemens", periods=["Q2 FY2026", "Q2 FY2025"], scopes=["Group", "Digital Industries", "Smart Infrastructure", "Mobility"]),
        ],
        examples=[
            ExampleGroup(category="Analytics", questions=["What were Henkel H1 2026 sales?", "What was Mercedes-Benz Group revenue in H1 2026?"]),
            ExampleGroup(category="Definitions", questions=["How does Henkel define organic sales growth?"]),
            ExampleGroup(category="Variance explanation", questions=["What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?"]),
            ExampleGroup(category="Management commentary", questions=["What did management report about Mercedes-Benz Mobility EBIT in Q2 2026?"]),
            ExampleGroup(category="Reconciliation", questions=["Reconcile Henkel Adhesive Technologies organic growth in H1 2026."]),
            ExampleGroup(category="Governance example", questions=["How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?"]),
        ],
        retrieval_model="none (public numerical-only demo)" if settings.public_demo else "sentence-transformers/all-MiniLM-L6-v2",
        retrieval_method="disabled; document-dependent answers refuse" if settings.public_demo else "metadata-first dense semantic retrieval",
        retrieval_version="public-numerical-demo-1.0.0" if settings.public_demo else "governed-semantic-dense-1.0.0",
        top_k=5, graph_version="step7-langgraph-1.0.0",
        verifier_version="deterministic-verifier-2.1.0", demo_mode=settings.is_demo,
        rights_notice="Only derived outputs, short governed citations, and official source links are exposed; raw reports and retrieval corpora remain private.",
        labels=product_catalog(ROOT).labels(),
        provider_mode='test' if settings.public_demo or settings.is_test else 'live',
    )
