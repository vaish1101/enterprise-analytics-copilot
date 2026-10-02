"""Deterministic evidence-unit construction helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from .models import EvidenceMethod, EvidenceRelevance, EvidenceUnit, EvidenceUnitType, SourceHierarchy


PARSER_VERSION = "pdf-pypdf-structure-1.0.0"
CHUNKING_VERSION = "governed-structure-1.0.0"


def normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def deterministic_evidence_id(
    *, source_id: str, page_number: int, unit_type: EvidenceUnitType, ordinal: int, text: str
) -> str:
    payload = {
        "source_id": source_id,
        "page_number": page_number,
        "unit_type": unit_type.value,
        "ordinal": ordinal,
        "content_hash": content_hash(text),
        "parser_version": PARSER_VERSION,
        "chunking_version": CHUNKING_VERSION,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"eu_{digest[:24]}"


def make_evidence_unit(
    *,
    source: dict[str, str],
    page_number: int,
    printed_page_or_slide: str,
    section: str,
    text: str,
    unit_type: EvidenceUnitType,
    relevance: EvidenceRelevance,
    ordinal: int,
    reporting_periods: Iterable[str],
    business_scopes: Iterable[str],
    metric_ids: Iterable[str],
    subsection: str | None = None,
    table_title: str | None = None,
    table_headers: Iterable[str] = (),
    neighboring_context: str | None = None,
) -> EvidenceUnit:
    cleaned = normalize_text(text)
    hierarchy = SourceHierarchy.CORROBORATING if source["source_id"] == "mercedes_q2_2026_interim_report" else SourceHierarchy.PRIMARY
    method = EvidenceMethod.TABLE_EXTRACTION if unit_type in {
        EvidenceUnitType.TABLE, EvidenceUnitType.TABLE_ROW, EvidenceUnitType.BRIDGE_DECOMPOSITION
    } else EvidenceMethod.DOCUMENT_TEXT
    return EvidenceUnit(
        evidence_unit_id=deterministic_evidence_id(
            source_id=source["source_id"], page_number=page_number,
            unit_type=unit_type, ordinal=ordinal, text=cleaned,
        ),
        source_id=source["source_id"],
        company_id=source["company"],
        source_title=source["source_title"],
        source_type=source["source_type"],
        reporting_periods=tuple(sorted(set(reporting_periods))),
        publication_date=source["publication_date"],
        page_number=page_number,
        printed_page_or_slide=printed_page_or_slide,
        section=section,
        subsection=subsection,
        table_title=table_title,
        table_headers=tuple(table_headers),
        business_scopes=tuple(sorted(set(business_scopes))),
        metric_ids=tuple(sorted(set(metric_ids))),
        metric_families=(),
        evidence_unit_type=unit_type,
        evidence_relevance=relevance,
        source_hierarchy=hierarchy,
        evidence_method=method,
        text=cleaned,
        neighboring_context=normalize_text(neighboring_context) if neighboring_context else None,
        official_url=source["official_url"],
        content_hash=content_hash(cleaned),
        parser_version=PARSER_VERSION,
        chunking_version=CHUNKING_VERSION,
    )
