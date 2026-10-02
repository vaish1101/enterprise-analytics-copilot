"""Naive fixed-token baseline used only for the controlled experiment."""

from __future__ import annotations

import re

from .evidence_units import make_evidence_unit
from .models import EvidenceRelevance, EvidenceUnit, EvidenceUnitType


def naive_fixed_chunks(structured_units: list[EvidenceUnit], *, tokens_per_chunk: int = 180) -> list[EvidenceUnit]:
    pages: dict[tuple[str, int], EvidenceUnit] = {}
    for unit in structured_units:
        pages.setdefault((unit.source_id, unit.page_number), unit)
        if len(unit.text) > len(pages[(unit.source_id, unit.page_number)].text):
            pages[(unit.source_id, unit.page_number)] = unit
    chunks: list[EvidenceUnit] = []
    for base in pages.values():
        words = re.findall(r"\S+", base.text)
        source = {
            "source_id": base.source_id, "company": base.company_id,
            "source_title": base.source_title, "source_type": base.source_type,
            "publication_date": base.publication_date, "official_url": base.official_url,
        }
        for ordinal, start in enumerate(range(0, len(words), tokens_per_chunk)):
            text = " ".join(words[start:start + tokens_per_chunk])
            chunks.append(make_evidence_unit(
                source=source, page_number=base.page_number,
                printed_page_or_slide=base.printed_page_or_slide,
                section=f"Fixed token chunk {ordinal + 1}", text=text,
                unit_type=EvidenceUnitType.NARRATIVE_SECTION,
                relevance=EvidenceRelevance.COMMENTARY, ordinal=ordinal,
                reporting_periods=base.reporting_periods,
                business_scopes=base.business_scopes, metric_ids=base.metric_ids,
            ))
    return chunks
