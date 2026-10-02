#!/usr/bin/env python3
"""Acquire and validate manifest-listed investor-relations source files.

The script deliberately uses ordinary HTTPS requests only. It does not automate a
browser, bypass access controls, or infer alternative download locations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "source_manifest.csv"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw_sources"
COMPANY_ALIASES = {
    "henkel": "henkel",
    "mercedes": "mercedes_benz_group",
}
SYSTEM_CA_CANDIDATES = (
    Path("/etc/ssl/cert.pem"),
    Path("/private/etc/ssl/cert.pem"),
)


class AcquisitionError(RuntimeError):
    """Raised when an acquisition or validation control fails."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        content_type: str = "",
        status_name: str = "failed",
    ) -> None:
        super().__init__(message)
        self.status = status
        self.content_type = content_type
        self.status_name = status_name


def validate_raw_dir(raw_dir: Path) -> Path:
    """Resolve and constrain acquisition output to the protected raw-data root."""

    approved_root = DEFAULT_RAW_DIR.resolve(strict=False)
    candidate = raw_dir.expanduser().resolve(strict=False)
    try:
        candidate.relative_to(approved_root)
    except ValueError as exc:
        raise AcquisitionError(
            f"Unsafe raw output path {candidate}; output must remain inside {approved_root}",
            status_name="failed_unsafe_output_path",
        ) from exc
    return candidate


def safe_destination(raw_dir: Path, expected_filename: str) -> Path:
    """Return a non-escaping destination for one manifest filename."""

    protected_dir = validate_raw_dir(raw_dir)
    filename = Path(expected_filename)
    if not expected_filename or filename.name != expected_filename or expected_filename in {".", ".."}:
        raise AcquisitionError(
            f"Unsafe manifest filename: {expected_filename!r}",
            status_name="failed_unsafe_output_path",
        )
    destination = (protected_dir / filename).resolve(strict=False)
    approved_root = DEFAULT_RAW_DIR.resolve(strict=False)
    try:
        destination.relative_to(approved_root)
    except ValueError as exc:
        raise AcquisitionError(
            f"Destination escapes protected raw root: {destination}",
            status_name="failed_unsafe_output_path",
        ) from exc
    return destination


class ControlledRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow a small number of HTTPS redirects on the original official host."""

    def __init__(self, allowed_host: str, max_redirects: int = 3) -> None:
        super().__init__()
        self.allowed_host = allowed_host.lower()
        self.max_redirects = max_redirects
        self.redirects: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != self.allowed_host:
            raise AcquisitionError(
                f"Rejected redirect outside the official HTTPS host: {newurl}",
                status=code,
                status_name="failed_redirect_anomaly",
            )
        if len(self.redirects) >= self.max_redirects:
            raise AcquisitionError(
                f"Rejected redirect chain longer than {self.max_redirects}",
                status=code,
                status_name="failed_redirect_anomaly",
            )
        self.redirects.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class ValidatedFile:
    path: Path
    sha256: str
    byte_size: int
    content_type: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_content_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


def verified_ssl_context() -> ssl.SSLContext:
    """Build a verified TLS context, using the macOS system bundle when needed."""

    defaults = ssl.get_default_verify_paths()
    if defaults.cafile and Path(defaults.cafile).is_file():
        return ssl.create_default_context()
    for candidate in SYSTEM_CA_CANDIDATES:
        if candidate.is_file():
            return ssl.create_default_context(cafile=str(candidate))
    return ssl.create_default_context()


def curl_verified_download(url: str, destination: Path) -> tuple[int, str, str]:
    """Use the system's verified TLS client when Python lacks the issuer chain.

    Redirects are not followed in this fallback, so the official manifest URL
    remains the only contacted document endpoint.
    """

    curl = shutil.which("curl")
    if curl is None:
        raise AcquisitionError(
            "Python certificate validation failed and no verified curl fallback is available",
            status_name="failed_network",
        )
    result = subprocess.run(
        [
            curl,
            "--fail",
            "--silent",
            "--show-error",
            "--proto",
            "=https",
            "--max-redirs",
            "0",
            "--output",
            str(destination),
            "--write-out",
            "%{http_code}\n%{content_type}\n%{url_effective}",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"curl exited with status {result.returncode}"
        raise AcquisitionError(
            f"Verified curl fallback failed: {detail}",
            status_name="failed_network",
        )
    lines = result.stdout.splitlines()
    if len(lines) != 3:
        raise AcquisitionError(
            "Verified curl fallback returned malformed transfer metadata",
            status_name="failed_network",
        )
    status = int(lines[0])
    if status != 200:
        raise AcquisitionError(
            f"Unexpected HTTP status {status}",
            status=status,
            content_type=lines[1],
            status_name=f"failed_http_{status}",
        )
    if lines[2] != url:
        raise AcquisitionError(
            f"Verified curl fallback changed the effective URL: {lines[2]}",
            status=status,
            content_type=lines[1],
            status_name="failed_redirect_anomaly",
        )
    return status, lines[1], lines[2]


def validate_source_file(
    path: Path,
    expected_content_type: str,
    observed_content_type: str,
) -> ValidatedFile:
    """Validate media type and file signature without trusting the extension."""

    expected = normalized_content_type(expected_content_type)
    observed = normalized_content_type(observed_content_type)
    with path.open("rb") as handle:
        prefix = handle.read(512)

    lowered = prefix.lstrip().lower()
    if lowered.startswith(b"<html") or lowered.startswith(b"<!doctype html"):
        raise AcquisitionError(
            "Received HTML instead of the expected source document",
            content_type=observed,
            status_name="failed_html_response",
        )
    if observed != expected:
        raise AcquisitionError(
            f"Unexpected content type: expected {expected!r}, received {observed!r}",
            content_type=observed,
            status_name="failed_content_type",
        )

    if expected == "application/pdf":
        if not prefix.startswith(b"%PDF-"):
            raise AcquisitionError(
                "File does not have a PDF signature",
                content_type=observed,
                status_name="failed_signature",
            )
    elif expected == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        if not zipfile.is_zipfile(path):
            raise AcquisitionError(
                "File is not a valid XLSX ZIP container",
                content_type=observed,
                status_name="failed_signature",
            )
        with zipfile.ZipFile(path) as archive:
            required_members = {"[Content_Types].xml", "xl/workbook.xml"}
            missing = required_members.difference(archive.namelist())
        if missing:
            raise AcquisitionError(
                f"XLSX container is missing required members: {sorted(missing)}",
                content_type=observed,
                status_name="failed_signature",
            )
    else:
        raise AcquisitionError(
            f"Manifest content type is not supported: {expected}",
            content_type=observed,
            status_name="failed_manifest_configuration",
        )

    return ValidatedFile(
        path=path,
        sha256=sha256_file(path),
        byte_size=path.stat().st_size,
        content_type=observed,
    )


def load_manifest(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise AcquisitionError("Manifest has no header")
        return list(reader), list(reader.fieldnames)


def save_manifest(path: Path, rows: Iterable[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".source_manifest.", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def install_without_overwrite(temp_path: Path, destination: Path, digest: str) -> str:
    """Install a validated file, refusing to replace different existing bytes."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing_digest = sha256_file(destination)
        if existing_digest == digest:
            temp_path.unlink(missing_ok=True)
            return "acquired_unchanged"
        quarantine_dir = destination.parent / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantine_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{destination.name}"
        quarantined = quarantine_dir / quarantine_name
        os.replace(temp_path, quarantined)
        raise AcquisitionError(
            f"Downloaded bytes differ from existing {destination.name}; candidate kept at {quarantined}",
            status_name="changed_source_review_required",
        )
    os.replace(temp_path, destination)
    return "acquired"


def write_metadata(destination: Path, row: dict[str, str], metadata: dict[str, object]) -> None:
    sidecar = destination.with_name(destination.name + ".metadata.json")
    payload = {
        "source_id": row["source_id"],
        "official_url": row["official_url"],
        "expected_filename": row["expected_filename"],
        **metadata,
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def acquire_http(row: dict[str, str], raw_dir: Path, timeout: int = 45) -> dict[str, object]:
    raw_dir = validate_raw_dir(raw_dir)
    destination = safe_destination(raw_dir, row["expected_filename"])
    parsed = urllib.parse.urlparse(row["official_url"])
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise AcquisitionError(
            "Manifest URL must be an absolute HTTPS URL",
            status_name="failed_manifest_configuration",
        )

    redirect_handler = ControlledRedirectHandler(parsed.hostname)
    opener = urllib.request.build_opener(
        redirect_handler,
        urllib.request.HTTPSHandler(context=verified_ssl_context()),
    )
    request = urllib.request.Request(
        row["official_url"],
        headers={
            "Accept": row["expected_content_type"],
            "User-Agent": "EnterpriseAnalyticsCopilot-source-acquisition/0.1",
        },
        method="GET",
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".source-download.", dir=raw_dir)
    os.close(fd)
    temp_path = Path(temp_name)
    observed_content_type = ""
    status = None
    final_url = row["official_url"]
    transfer_client = "python_urllib_verified"
    try:
        try:
            with opener.open(request, timeout=timeout) as response, temp_path.open("wb") as output:
                status = response.getcode()
                final_url = response.geturl()
                observed_content_type = response.headers.get("Content-Type", "")
                if status != 200:
                    raise AcquisitionError(
                        f"Unexpected HTTP status {status}",
                        status=status,
                        content_type=observed_content_type,
                        status_name=f"failed_http_{status}",
                    )
                shutil.copyfileobj(response, output)
        except urllib.error.HTTPError as exc:
            raise AcquisitionError(
                f"HTTP {exc.code} for {row['source_id']}",
                status=exc.code,
                content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
                status_name=f"blocked_http_{exc.code}" if exc.code in {401, 403} else f"failed_http_{exc.code}",
            ) from exc
        except urllib.error.URLError as exc:
            if "CERTIFICATE_VERIFY_FAILED" in str(exc.reason):
                status, observed_content_type, final_url = curl_verified_download(
                    row["official_url"], temp_path
                )
                transfer_client = "system_curl_verified_no_redirect"
            else:
                raise AcquisitionError(
                    f"Network error for {row['source_id']}: {exc.reason}",
                    status_name="failed_network",
                ) from exc

        validated = validate_source_file(
            temp_path,
            row["expected_content_type"],
            observed_content_type,
        )
        acquisition_status = install_without_overwrite(temp_path, destination, validated.sha256)
        metadata = {
            "acquisition_method": "http_get",
            "acquisition_status": acquisition_status,
            "retrieval_timestamp": utc_now(),
            "http_status": status,
            "observed_content_type": validated.content_type,
            "byte_size": validated.byte_size,
            "sha256": validated.sha256,
            "final_url": final_url,
            "redirects": redirect_handler.redirects,
            "transfer_client": transfer_client,
        }
        write_metadata(destination, row, metadata)
        return metadata
    except AcquisitionError as exc:
        if exc.status is None:
            exc.status = status
        if not exc.content_type:
            exc.content_type = normalized_content_type(observed_content_type)
        raise
    finally:
        temp_path.unlink(missing_ok=True)


def acquire_manual(row: dict[str, str], supplied_path: Path, raw_dir: Path) -> dict[str, object]:
    raw_dir = validate_raw_dir(raw_dir)
    destination = safe_destination(raw_dir, row["expected_filename"])
    if not supplied_path.is_file():
        raise AcquisitionError(
            f"Manual source file does not exist: {supplied_path}",
            status_name="failed_manual_file_missing",
        )
    if supplied_path.name != row["expected_filename"]:
        raise AcquisitionError(
            f"Manual filename must be exactly {row['expected_filename']!r}",
            status_name="failed_manual_filename",
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".manual-source.", dir=raw_dir)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copyfile(supplied_path, temp_path)
        validated = validate_source_file(
            temp_path,
            row["expected_content_type"],
            row["expected_content_type"],
        )
        install_status = install_without_overwrite(temp_path, destination, validated.sha256)
        acquisition_status = "acquired_manual" if install_status == "acquired" else "acquired_manual_unchanged"
        metadata = {
            "acquisition_method": "manual_local_file",
            "acquisition_status": acquisition_status,
            "retrieval_timestamp": utc_now(),
            "http_status": "",
            "observed_content_type": validated.content_type,
            "byte_size": validated.byte_size,
            "sha256": validated.sha256,
            "final_url": row["official_url"],
            "redirects": [],
        }
        write_metadata(destination, row, metadata)
        return metadata
    finally:
        temp_path.unlink(missing_ok=True)


def apply_metadata(row: dict[str, str], metadata: dict[str, object]) -> None:
    for field in (
        "acquisition_status",
        "sha256",
        "retrieval_timestamp",
        "http_status",
        "observed_content_type",
        "byte_size",
    ):
        row[field] = str(metadata.get(field, ""))
    row["acquisition_notes"] = "Validated successfully; see gitignored metadata sidecar."


def apply_failure(row: dict[str, str], failure: AcquisitionError) -> None:
    row["acquisition_status"] = failure.status_name
    row["retrieval_timestamp"] = utc_now()
    row["http_status"] = "" if failure.status is None else str(failure.status)
    row["observed_content_type"] = normalized_content_type(failure.content_type)
    row["byte_size"] = ""
    row["sha256"] = ""
    row["acquisition_notes"] = str(failure)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--company", choices=sorted(COMPANY_ALIASES), help="Acquire one company's sources")
    mode.add_argument("--all", action="store_true", help="Acquire all manifest sources")
    mode.add_argument(
        "--manual-file",
        nargs=2,
        metavar=("SOURCE_ID", "PATH"),
        help="Validate and register an official file downloaded manually",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        args.raw_dir = validate_raw_dir(args.raw_dir)
    except AcquisitionError as exc:
        print(f"raw-dir: {exc.status_name}: {exc}", file=sys.stderr)
        return 2
    rows, fieldnames = load_manifest(args.manifest)
    by_id = {row["source_id"]: row for row in rows}
    failures = 0

    if args.manual_file:
        source_id, supplied = args.manual_file
        row = by_id.get(source_id)
        if row is None:
            print(f"Unknown source_id: {source_id}", file=sys.stderr)
            return 2
        try:
            metadata = acquire_manual(row, Path(supplied).expanduser().resolve(), args.raw_dir)
            apply_metadata(row, metadata)
            print(f"{source_id}: {metadata['acquisition_status']} ({metadata['byte_size']} bytes)")
        except AcquisitionError as exc:
            apply_failure(row, exc)
            print(f"{source_id}: {exc.status_name}: {exc}", file=sys.stderr)
            failures += 1
    else:
        selected_company = COMPANY_ALIASES.get(args.company) if args.company else None
        selected = rows if args.all else [row for row in rows if row["company"] == selected_company]
        for row in selected:
            try:
                metadata = acquire_http(row, args.raw_dir)
                apply_metadata(row, metadata)
                print(
                    f"{row['source_id']}: {metadata['acquisition_status']} "
                    f"({metadata['byte_size']} bytes, sha256={metadata['sha256']})"
                )
            except AcquisitionError as exc:
                apply_failure(row, exc)
                print(f"{row['source_id']}: {exc.status_name}: {exc}", file=sys.stderr)
                failures += 1

    save_manifest(args.manifest, rows, fieldnames)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
