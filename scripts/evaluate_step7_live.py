"""Controlled real-provider evaluation; refuses to substitute fake results."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from scripts.evaluate_step6 import evaluate
from src.evaluation.run_manifest import build_run_manifest, write_manifest
from src.llm.provider import provider_from_environment
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import build_default_retriever


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--core-freeze-hash", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    provider = provider_from_environment(allow_fake=False)
    dataset = ROOT / f"evals/step7_live_{args.split}.jsonl"
    cases = [json.loads(line) for line in dataset.read_text().splitlines() if line]
    units = [EvidenceUnit.model_validate_json(line) for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text().splitlines() if line]
    graph = EnterpriseAnalyticsGraph(
        ROOT, provider=provider, retriever=build_default_retriever(units, root=ROOT),
        max_provider_attempts=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )
    metrics, failures = evaluate(cases, graph)
    output = Path(args.output)
    report = {"split": args.split, "live": True, "provider": provider.name, "model": provider.model,
              "metrics": metrics, "failures": failures}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    manifest = build_run_manifest(
        ROOT, run_id=f"step7-live-{args.split}", provider=provider.name, model=provider.model,
        model_settings={"max_attempts": int(os.getenv("LLM_MAX_RETRIES", "2")),
                        "timeout_seconds": float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))},
        core_freeze_hash=args.core_freeze_hash, evaluation_dataset=dataset,
    )
    write_manifest(output.with_suffix(".manifest.json"), manifest)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__": main()

