"""Secret-free, hash-addressed evaluation run manifests."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

from pydantic import BaseModel, ConfigDict

from src.orchestration.prompts import PROMPT_VERSIONS


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class PromptFingerprint(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    filename: str
    version: str
    sha256: str


class RunManifest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    run_id: str
    timestamp: datetime
    git_commit: str | None
    provider: str
    model: str
    model_settings: dict[str, str | int | float]
    prompt_fingerprints: tuple[PromptFingerprint, ...]
    core_freeze_hash: str
    source_manifest_hash: str
    metric_catalog_hash: str
    evaluation_dataset_hash: str
    retrieval_index_version: str
    graph_version: str
    verifier_version: str
    package_versions: dict[str, str]


def build_run_manifest(root: Path, *, run_id: str, provider: str, model: str,
                       model_settings: dict[str, str | int | float], core_freeze_hash: str,
                       evaluation_dataset: Path) -> RunManifest:
    prompts = tuple(PromptFingerprint(
        filename=f"prompts/{name}.md", version=version,
        sha256=sha256_file(root / "prompts" / f"{name}.md"),
    ) for name, version in sorted(PROMPT_VERSIONS.items()))
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=2,
        )
        git_commit = commit.stdout.strip() if commit.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        git_commit = None
    packages = {}
    for name in ("langgraph", "openai", "pydantic", "sentence-transformers"):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = "not-installed"
    return RunManifest(
        run_id=run_id, timestamp=datetime.now(UTC), git_commit=git_commit,
        provider=provider, model=model, model_settings=model_settings,
        prompt_fingerprints=prompts, core_freeze_hash=core_freeze_hash,
        source_manifest_hash=sha256_file(root / "data/source_manifest.csv"),
        metric_catalog_hash=sha256_file(root / "config/metric_catalog.csv"),
        evaluation_dataset_hash=sha256_file(evaluation_dataset),
        retrieval_index_version="sentence-transformers/all-MiniLM-L6-v2::governed-semantic-dense-1.0.0",
        graph_version="step7-langgraph-1.0.0", verifier_version="deterministic-verifier-2.0.0",
        package_versions=packages,
    )


def write_manifest(path: Path, manifest: RunManifest) -> None:
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
