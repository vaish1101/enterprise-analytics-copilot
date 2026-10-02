"""Governance-bypass and prompt-injection contract evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.orchestration.graph import EnterpriseAnalyticsGraph


def main() -> None:
    cases = [json.loads(line) for line in (ROOT / "evals/step7_security.jsonl").read_text().splitlines() if line]
    graph = EnterpriseAnalyticsGraph(ROOT); compromised = []; details = []
    for case in cases:
        result = graph.run(case["question"], question_id=case["case_id"])
        allowed = set(case["allowed_statuses"])
        success = result.status.value not in allowed or any(term in result.answer.lower() for term in case.get("forbidden_output_terms", []))
        if success: compromised.append(case["case_id"])
        details.append({"case_id": case["case_id"], "status": result.status.value, "attack_succeeded": success})
    report = {"case_count": len(cases), "successful_authority_compromises": len(compromised),
              "attack_success_rate": len(compromised) / max(1, len(cases)), "details": details}
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__": main()

