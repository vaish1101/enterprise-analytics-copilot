"""Report development and frozen-test metrics for the Step 3 planning layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_planner import evaluate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, default=ROOT / "evals/dev.jsonl")
    parser.add_argument("--test", type=Path, default=ROOT / "evals/test.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {
        "development": evaluate(args.development, ROOT),
        "test": evaluate(args.test, ROOT),
    }
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if result["development"]["failed"] or result["test"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
