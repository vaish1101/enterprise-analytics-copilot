from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.retrieval.evidence_units import (
    CHUNKING_VERSION,
    PARSER_VERSION,
    deterministic_evidence_id,
)
from src.retrieval.models import EvidenceUnitType
from src.retrieval.parser import PDF_SOURCES, parse_corpus


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def units():
    return parse_corpus(ROOT)


def test_evidence_unit_ids_are_deterministic():
    kwargs = dict(source_id="source", page_number=7, unit_type=EvidenceUnitType.TABLE, ordinal=2, text="same text")
    assert deterministic_evidence_id(**kwargs) == deterministic_evidence_id(**kwargs)
    assert deterministic_evidence_id(**kwargs) != deterministic_evidence_id(**{**kwargs, "text": "different"})


def test_parser_and_chunking_versions_are_recorded(units):
    assert {unit.parser_version for unit in units} == {PARSER_VERSION}
    assert {unit.chunking_version for unit in units} == {CHUNKING_VERSION}


def test_only_four_approved_pdfs_are_ingested(units):
    assert {unit.source_id for unit in units} == set(PDF_SOURCES)
    assert all(unit.source_type == "pdf" for unit in units)
    assert not any("xlsx" in unit.source_id for unit in units)


def test_source_ownership_is_preserved(units):
    ownership = {unit.source_id: unit.company_id for unit in units}
    assert ownership["henkel_h1_2026_financial_report"] == "henkel"
    assert all(ownership[source] == "mercedes_benz_group" for source in PDF_SOURCES if source.startswith("mercedes"))


def test_period_and_scope_metadata_are_preserved(units):
    page = next(unit for unit in units if unit.source_id == "mercedes_q2_2026_fact_sheet_pdf" and unit.page_number == 19 and unit.evidence_unit_type is EvidenceUnitType.TABLE)
    assert {"Q2_2026", "H1_2026"}.issubset(page.reporting_periods)
    assert page.business_scopes == ("mercedes_cars",)


def test_table_title_and_headers_are_preserved(units):
    tables = [unit for unit in units if unit.evidence_unit_type in {EvidenceUnitType.TABLE, EvidenceUnitType.TABLE_ROW}]
    assert tables
    assert all(unit.table_title and unit.table_headers for unit in tables)


def test_definition_is_preserved_as_an_atomic_unit(units):
    definitions = [unit for unit in units if unit.evidence_unit_type is EvidenceUnitType.METRIC_DEFINITION]
    assert any("adjusted for foreign exchange effects and acquisitions/divestments" in unit.text for unit in definitions)


def test_footnotes_retain_neighboring_context(units):
    footnotes = [unit for unit in units if unit.evidence_unit_type is EvidenceUnitType.FOOTNOTE]
    assert footnotes and all(unit.neighboring_context for unit in footnotes)


def test_all_governed_evidence_types_exist(units):
    assert {unit.evidence_unit_type for unit in units} == set(EvidenceUnitType)


def test_invalid_source_manifest_is_rejected(tmp_path):
    (tmp_path / "data").mkdir()
    rows = list(csv.DictReader((ROOT / "data/source_manifest.csv").open()))
    rows = [row for row in rows if row["source_id"] in PDF_SOURCES][:-1]
    with (tmp_path / "data/source_manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="approved PDF corpus"):
        parse_corpus(tmp_path)


def test_invalid_company_source_combination_is_rejected(tmp_path):
    (tmp_path / "data").mkdir()
    rows = [row for row in csv.DictReader((ROOT / "data/source_manifest.csv").open()) if row["source_id"] in PDF_SOURCES]
    rows[0]["company"] = "mercedes_benz_group"
    with (tmp_path / "data/source_manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="invalid company/source combination"):
        parse_corpus(tmp_path)


def test_content_hash_matches_repeated_build(units):
    rebuilt = parse_corpus(ROOT)
    assert [(u.evidence_unit_id, u.content_hash) for u in units] == [(u.evidence_unit_id, u.content_hash) for u in rebuilt]
