"""Offline publication checks. Never emit matched secret values or read ignored secrets."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = {"data_contracts.md", "henkel_extraction_decision.md", "mercedes_xlsx_mapping.md", "architecture.md", "methodology.md", "evaluation.md", "provenance_and_verification.md", "data_sources.md", "limitations.md", "reproduction.md", "deployment.md", "publication_readiness.md", "public_file_inventory.csv"}
PUBLIC_DOCS.update({"final_release_status.md", "release_candidate_architecture.md",
                    "release_candidate_demo.md", "release_candidate_evaluation.md"})
RULES = {
    "credential_prefix": re.compile(rb"(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,})"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal_machine_path": re.compile(rb"/(?:Users|home)/(?!example(?:/|$))[^/\s<>\"']+/"),
    "development_password_default": re.compile(b"local-development" + b"-only"),
    "bearer_literal": re.compile(rb"(?i)bearer[ \t]+[A-Za-z0-9._-]{24,}"),
    "private_runtime_path": re.compile(rb"/pri[v]ate/(?:var|tmp)/[^\s\"'<>]+"),
    "personal_email": re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}

def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)

def candidates() -> list[str]:
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    return sorted({name for name in names if name and (ROOT / name).is_file()})

def restricted(name: str) -> bool:
    parts = Path(name).parts
    return (name.startswith(("data/raw_sources/", "data/retrieval/local/", "data/checkpoints/", ".publication-private/", "tmp/"))
            or any(p in {"node_modules", "__pycache__", ".venv", ".pytest_cache"} for p in parts)
            or Path(name).name.startswith(".env") and name != ".env.example"
            or name.endswith((".pdf", ".xlsx", ".xls", ".sqlite", ".db", ".dump", ".safetensors", ".pt", ".npy", ".npz", ".log")))

def category(name: str) -> tuple[str, str]:
    if restricted(name): return "PRIVATE / DO NOT PUBLISH", "Excluded raw, local, runtime or secret boundary"
    if name.startswith("artifacts/"): return "INTERNAL DEVELOPMENT", "Historical runtime/evaluation output; retain privately"
    if name.startswith("docs/") and Path(name).name not in PUBLIC_DOCS: return "MOVE / CURATE", "Historical report or prototype; preserve in private archive"
    if name == "render.yaml": return "REVIEW REQUIRED", "Unvalidated deployment template; not public deployment evidence"
    return "KEEP PUBLIC", "Source, contract, safe metadata, test or curated documentation"

def inventory() -> str:
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(("path", "classification", "reason"))
    for name in candidates(): writer.writerow((name, *category(name)))
    for name in ("data/raw_sources/", "data/retrieval/local/", "data/checkpoints/", ".env", ".publication-private/", "tmp/", "frontend/node_modules/", "frontend/dist/"):
        writer.writerow((name, "PRIVATE / DO NOT PUBLISH" if not name.endswith(("node_modules/", "dist/")) else "DELETE SAFE", "Local-only boundary; contents not inventoried or exposed"))
    return out.getvalue()

def findings(name: str, data: bytes) -> list[dict]:
    hits = [{"path": name, "category": kind} for kind, pattern in RULES.items() if pattern.search(data)]
    if restricted(name): hits.append({"path": name, "category": "restricted_asset"})
    # Credential-bearing DSNs must be placeholders or explicit failure fixtures.
    if not name.startswith(("tests/", "scripts/evaluate_step8_5.py")):
        for match in re.finditer(rb"postgres(?:ql)?://([^:\s\"']+):([^@\s\"']+)@", data):
            if not match.group(1).startswith(b"${") or not match.group(2).startswith(b"${"):
                hits.append({"path": name, "category": "credential_dsn"}); break
        if re.search(rb"(?:mysql|redis|mongodb(?:\+srv)?|https?)://[^\s/:@]+:[^\s/@]+@", data):
            hits.append({"path": name, "category": "credential_url"})
        if re.search(rb"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*[\"'][A-Za-z0-9_+/-]{24,}[\"']", data):
            hits.append({"path": name, "category": "credential_assignment"})
    return hits

def links(names: list[str]) -> list[dict]:
    errors = []
    for name in names:
        if name.endswith(".svg"):
            try:
                root = ET.fromstring((ROOT / name).read_text())
                if root.tag != "{http://www.w3.org/2000/svg}svg" or not root.get("viewBox"): raise ValueError()
            except (ET.ParseError, ValueError): errors.append({"path": name, "category": "invalid_svg"})
        if name != "README.md" and not (name.startswith("docs/") and name.endswith(".md")): continue
        text = (ROOT / name).read_text()
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.split("#", 1)[0].split(" ", 1)[0]
            if not target or re.match(r"https?://|mailto:", target): continue
            if target.startswith("/") or not ((ROOT / name).parent / target).resolve().exists():
                errors.append({"path": name, "category": "broken_or_absolute_link", "target": target})
    return errors

def check(history: bool) -> dict:
    names = candidates(); current = []
    for name in names: current.extend(findings(name, (ROOT / name).read_bytes()))
    current.extend(links(names))
    env = ROOT / ".env.example"
    if env.exists():
        for line in env.read_text().splitlines():
            if line and not line.startswith("#") and ("=" not in line or line.split("=", 1)[1].strip()):
                current.append({"path": ".env.example", "category": "nonempty_placeholder"}); break
    staged = []
    for name in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0"):
        if name: staged.extend(findings(name, git("show", ":" + name)))
    historical = []; historical_internal = []; blobs = 0
    if history:
        seen = set()
        for line in git("rev-list", "--objects", "--all").decode().splitlines():
            oid, _, name = line.partition(" ")
            if oid in seen or git("cat-file", "-t", oid).strip() != b"blob": continue
            seen.add(oid); blobs += 1
            historical.extend(findings(name or "unnamed_blob", git("cat-file", "blob", oid)))
            if name and category(name)[0] in {"INTERNAL DEVELOPMENT", "MOVE / CURATE", "REVIEW REQUIRED"}:
                historical_internal.append({"path": name, "category": "internal_history_review"})
    return {"candidate_files": len(names), "current_findings": current, "staged_findings": staged,
            "history_blobs": blobs, "history_findings": historical, "history_internal_review": historical_internal,
            "scope": "Candidate + staged + optional reachable history; ignored private contents are not read; pattern scan is not universal secret detection"}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--inventory", action="store_true"); parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    if args.inventory: print(inventory(), end=""); return
    report = check(args.history); print(json.dumps(report, indent=2))
    if report["current_findings"] or report["staged_findings"] or report["history_findings"] or report["history_internal_review"]: sys.exit(1)

if __name__ == "__main__": main()
