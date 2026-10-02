"""Build the ignored local Step 5 document corpus."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.retrieval.parser import parse_corpus


OUTPUT = ROOT / "data/retrieval/local/evidence_units.jsonl"
STATS = ROOT / "data/retrieval/local/corpus_stats.json"


def build() -> tuple[list, dict]:
    units = parse_corpus(ROOT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(unit.model_dump_json() for unit in units) + "\n", encoding="utf-8")
    token_counts = [len(unit.text.split()) for unit in units]
    stats = {
        "documents": len({unit.source_id for unit in units}),
        "pages_or_slides": len({(unit.source_id, unit.page_number) for unit in units}),
        "evidence_units": len(units),
        "evidence_units_by_type": dict(sorted(Counter(unit.evidence_unit_type.value for unit in units).items())),
        "average_tokens": round(statistics.mean(token_counts), 2),
        "median_tokens": statistics.median(token_counts),
        "max_tokens": max(token_counts),
        "company_distribution": dict(sorted(Counter(unit.company_id for unit in units).items())),
        "source_distribution": dict(sorted(Counter(unit.source_id for unit in units).items())),
        "embedding_count": len(units),
        "indexed_count": len(units),
    }
    STATS.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return units, stats


if __name__ == "__main__":
    _, result = build()
    print(json.dumps(result, indent=2, sort_keys=True))
