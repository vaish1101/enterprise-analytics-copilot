"""Frozen Siemens retrieval and agentic benchmarks using unchanged core algorithms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from scripts.evaluate_step5 import evaluate as evaluate_retrieval
from scripts.evaluate_step6 import evaluate as evaluate_agentic
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import build_default_retriever


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    units = [EvidenceUnit.model_validate_json(line) for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text().splitlines() if line]
    retriever = build_default_retriever(units, root=ROOT)
    retrieval_metrics, retrieval_failures = evaluate_retrieval(
        units, _load(ROOT / "evals/step7_siemens_retrieval_test.jsonl"), "dense", retriever=retriever,
    )
    graph = EnterpriseAnalyticsGraph(ROOT, retriever=retriever)
    agent_metrics, agent_failures = evaluate_agentic(
        _load(ROOT / "evals/step7_siemens_agent_test.jsonl"), graph,
    )
    report = {"benchmark_version": "step7-siemens-initial-1.0.0",
              "retrieval": retrieval_metrics, "retrieval_failures": retrieval_failures,
              "agentic": agent_metrics, "agentic_failures": agent_failures}
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__": main()

