import ssl
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pytest

from scripts.acquire_sources import (
    DEFAULT_RAW_DIR, PROJECT_ROOT, AcquisitionError, ControlledRedirectHandler,
    acquire_manual, install_without_overwrite, safe_destination,
    validate_raw_dir, validate_source_file, verified_ssl_context,
)


def test_tls_context_requires_certificate_validation():
    context = verified_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_valid_pdf_signature_is_accepted(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(b"%PDF-1.7\nminimal-test-content")
    result = validate_source_file(path, "application/pdf", "application/pdf")
    assert len(result.sha256) == 64


def test_minimal_valid_xlsx_container_is_accepted(tmp_path):
    path = tmp_path / "source.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    result = validate_source_file(
        path,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert result.byte_size > 0


@pytest.mark.negative
def test_html_disguised_as_pdf_is_rejected(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(b"<!doctype html><title>Access denied</title>")
    with pytest.raises(AcquisitionError, match="HTML"):
        validate_source_file(path, "application/pdf", "application/pdf")


@pytest.mark.negative
def test_wrong_content_type_is_rejected(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(b"%PDF-1.7\ncontent")
    with pytest.raises(AcquisitionError, match="Unexpected content type"):
        validate_source_file(path, "application/pdf", "text/plain")


@pytest.mark.negative
def test_invalid_pdf_signature_is_rejected(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(AcquisitionError, match="PDF signature"):
        validate_source_file(path, "application/pdf", "application/pdf")


@pytest.mark.negative
def test_invalid_xlsx_signature_is_rejected(tmp_path):
    path = tmp_path / "source.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("unrelated.txt", "not a workbook")
    with pytest.raises(AcquisitionError, match="missing required members"):
        validate_source_file(
            path,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


@pytest.mark.negative
def test_cross_host_redirect_is_rejected():
    handler = ControlledRedirectHandler("official.example")
    request = urllib.request.Request("https://official.example/report.pdf")
    with pytest.raises(AcquisitionError, match="outside the official HTTPS host"):
        handler.redirect_request(
            request, None, 302, "Found", {}, "https://other.example/report.pdf"
        )


@pytest.mark.negative
def test_changed_existing_file_is_not_overwritten(tmp_path):
    destination = tmp_path / "source.pdf"
    destination.write_bytes(b"%PDF-1.7\noriginal")
    candidate = tmp_path / "candidate.pdf"
    candidate.write_bytes(b"%PDF-1.7\nchanged")
    with pytest.raises(AcquisitionError) as caught:
        install_without_overwrite(candidate, destination, "different-digest")
    assert caught.value.status_name == "changed_source_review_required"
    assert destination.read_bytes() == b"%PDF-1.7\noriginal"
    assert len(list((tmp_path / "quarantine").iterdir())) == 1


@pytest.mark.negative
def test_external_raw_output_path_is_rejected(tmp_path):
    with pytest.raises(AcquisitionError) as caught:
        validate_raw_dir(tmp_path)
    assert caught.value.status_name == "failed_unsafe_output_path"


@pytest.mark.negative
def test_project_root_output_path_is_rejected():
    with pytest.raises(AcquisitionError):
        validate_raw_dir(PROJECT_ROOT)


@pytest.mark.negative
def test_path_traversal_outside_raw_root_is_rejected():
    with pytest.raises(AcquisitionError):
        validate_raw_dir(DEFAULT_RAW_DIR / ".." / "docs")


@pytest.mark.negative
def test_manifest_filename_path_traversal_is_rejected():
    with pytest.raises(AcquisitionError):
        safe_destination(DEFAULT_RAW_DIR, "../docs/source.pdf")


@pytest.mark.negative
def test_symlink_escape_is_rejected(tmp_path):
    DEFAULT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=DEFAULT_RAW_DIR) as directory:
        link = Path(directory) / "escape"
        link.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(AcquisitionError):
            validate_raw_dir(link)


@pytest.mark.negative
def test_manual_file_with_unexpected_filename_is_rejected(tmp_path):
    supplied = tmp_path / "wrong.xlsx"
    supplied.write_bytes(b"not used because filename fails first")
    row = {
        "source_id": "mercedes_q2_2026_fact_sheet_xlsx",
        "official_url": "https://group.mercedes-benz.com/fact-sheet.xlsx",
        "expected_filename": "mercedes-benz-fact-sheet-q2-2026.xlsx",
        "expected_content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    with tempfile.TemporaryDirectory(dir=DEFAULT_RAW_DIR) as raw_dir:
        with pytest.raises(AcquisitionError) as caught:
            acquire_manual(row, supplied, Path(raw_dir))
    assert caught.value.status_name == "failed_manual_filename"
