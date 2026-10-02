"""Strict contracts for governed document evidence and retrieval results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceUnitType(str, Enum):
    NARRATIVE_SECTION = "NARRATIVE_SECTION"
    METRIC_DEFINITION = "METRIC_DEFINITION"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    BRIDGE_DECOMPOSITION = "BRIDGE_DECOMPOSITION"
    FOOTNOTE = "FOOTNOTE"
    GOVERNANCE_METHODOLOGY = "GOVERNANCE_METHODOLOGY"
    HEADLINE_SUMMARY = "HEADLINE_SUMMARY"


class EvidenceRelevance(str, Enum):
    REPORTED = "REPORTED"
    MANAGEMENT_ATTRIBUTED = "MANAGEMENT_ATTRIBUTED"
    DEFINITION = "DEFINITION"
    METHODOLOGY = "METHODOLOGY"
    COMMENTARY = "COMMENTARY"
    LIMITATION = "LIMITATION"


class SourceHierarchy(str, Enum):
    PRIMARY = "PRIMARY"
    CORROBORATING = "CORROBORATING"


class EvidenceMethod(str, Enum):
    DOCUMENT_TEXT = "DOCUMENT_TEXT"
    TABLE_EXTRACTION = "TABLE_EXTRACTION"
    GOVERNED_SOURCE_ADAPTER = "GOVERNED_SOURCE_ADAPTER"


class RetrievalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NO_RELEVANT_EVIDENCE = "NO_RELEVANT_EVIDENCE"
    REJECTED = "REJECTED"


class EvidenceUnit(BaseModel):
    """A source-owned, deterministic, citation-ready unit."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_unit_id: str = Field(pattern=r"^eu_[0-9a-f]{24}$")
    source_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    reporting_periods: tuple[str, ...]
    publication_date: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    printed_page_or_slide: str = Field(min_length=1)
    section: str = Field(min_length=1)
    subsection: str | None = None
    table_title: str | None = None
    table_headers: tuple[str, ...] = ()
    business_scopes: tuple[str, ...]
    metric_ids: tuple[str, ...]
    metric_families: tuple[str, ...] = ()
    evidence_unit_type: EvidenceUnitType
    evidence_relevance: EvidenceRelevance
    source_hierarchy: SourceHierarchy
    evidence_method: EvidenceMethod
    text: str = Field(min_length=1)
    neighboring_context: str | None = None
    official_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_version: str = Field(min_length=1)
    chunking_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def citation_metadata_complete(self) -> "EvidenceUnit":
        if self.evidence_unit_type in {EvidenceUnitType.TABLE, EvidenceUnitType.TABLE_ROW}:
            if not self.table_title or not self.table_headers:
                raise ValueError("table evidence must preserve title and headers")
        return self


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    query_id: str = Field(min_length=1)
    raw_question: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    reporting_periods: tuple[str, ...]
    business_scopes: tuple[str, ...]
    metric_ids: tuple[str, ...]
    preferred_evidence_types: tuple[EvidenceUnitType, ...] = ()
    top_k: int = Field(default=5, ge=1, le=20)


class EvidenceResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_unit_id: str
    source_id: str
    company_id: str
    source_title: str
    official_url: str
    page_number: int
    printed_page_or_slide: str
    section: str
    subsection: str | None
    table_title: str | None
    table_headers: tuple[str, ...]
    business_scopes: tuple[str, ...]
    reporting_periods: tuple[str, ...]
    evidence_unit_type: EvidenceUnitType
    evidence_relevance: EvidenceRelevance
    source_hierarchy: SourceHierarchy
    evidence_method: EvidenceMethod
    text: str
    metric_ids: tuple[str, ...]
    metric_families: tuple[str, ...]
    lexical_rank: int | None
    dense_rank: int | None
    fused_rank: int
    lexical_score: float | None
    dense_score: float | None
    fused_score: float
    content_hash: str
    citation: str = Field(min_length=1)


class RetrievalTrace(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    query: str
    plan_derived_filters: dict[str, tuple[str, ...] | str]
    expanded_terms: tuple[str, ...]
    retrieval_methods: tuple[str, ...]
    candidates_before_filtering: int
    candidates_after_filtering: int
    top_k: int
    final_evidence_ids: tuple[str, ...]
    latency_ms: float = Field(ge=0)
    parser_version: str
    chunking_version: str
    embedding_model: str
    embedding_index_version: str
    retrieval_strategy_version: str
    fusion_strategy_version: str


class RetrievalResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    status: RetrievalStatus
    results: tuple[EvidenceResult, ...]
    trace: RetrievalTrace
    reason: str | None = None

    @model_validator(mode="after")
    def status_matches_results(self) -> "RetrievalResponse":
        if self.status is RetrievalStatus.SUCCESS and not self.results:
            raise ValueError("SUCCESS requires evidence")
        if self.status is not RetrievalStatus.SUCCESS and self.results:
            raise ValueError("non-success retrieval cannot return evidence")
        return self
