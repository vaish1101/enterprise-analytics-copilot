"""Natural-language-shaped structured draft fault benchmark."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import ClaimType, VerificationVerdict


def mutate(draft, mutation: str, faulty_text: str):
    if mutation == "clean": return draft
    claims = list(draft.claims)
    index = 0
    if mutation in {"bridge_sign", "causal"}:
        index = next(i for i,c in enumerate(claims) if c.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED)
    claim = claims[index]; changes = {"text": faulty_text}
    if mutation == "wrong_number": changes["value"] = claim.value + Decimal("90")
    elif mutation == "rounded_number": changes["value"] = Decimal("10300")
    elif mutation == "wrong_unit": changes["unit"] = "USD_million"
    elif mutation == "wrong_period": changes["periods"] = ("Q2_2025",)
    elif mutation == "wrong_scope": changes["business_scope"] = "wrong_scope"
    elif mutation == "wrong_company": changes["company_id"] = "wrong_company"
    elif mutation == "wrong_metric": changes["metric_id"] = "wrong_metric"
    elif mutation == "bridge_sign": changes["value"] = -claim.value
    elif mutation == "causal": pass
    elif mutation in {"wrong_citation", "citation_laundering"}: changes["evidence_ids"] = ("eu_000000000000000000000000",)
    elif mutation == "missing_citation": changes["evidence_ids"] = ()
    elif mutation == "wrong_period_citation": changes["periods"] = ("Q1_1999",)
    elif mutation == "wrong_scope_citation": changes["business_scope"] = "wrong_scope"
    elif mutation == "provenance": changes.update({"claim_type": ClaimType.CALCULATED, "calculation_run_ids": ()})
    elif mutation == "missing_lineage": changes.update({"claim_type": ClaimType.CALCULATED, "calculation_run_ids": ()})
    elif mutation == "unsupported_interpretation": changes.update({"claim_type": ClaimType.INTERPRETATION, "fact_ids": (), "evidence_ids": (), "calculation_run_ids": (), "value": None, "unit": None})
    elif mutation == "rounding_omitted":
        return draft.model_copy(update={"limitations": (), "answer": faulty_text})
    elif mutation == "invented_percentage": changes.update({"claim_type": ClaimType.CALCULATED, "value": Decimal("-26"), "unit": "percent", "calculation_run_ids": ("run_invented",)})
    claims[index] = claim.model_copy(update=changes)
    return draft.model_copy(update={"claims": tuple(claims), "answer": " ".join(c.text for c in claims)})


def evaluate(split: str) -> dict:
    cases = [json.loads(line) for line in (ROOT / f"evals/step7_verifier_{split}.jsonl").read_text().splitlines() if line]
    detected = false_positives = positives = negatives = 0; details = []
    for case in cases:
        provider = DeterministicFakeProvider(); graph = EnterpriseAnalyticsGraph(ROOT, provider=provider)
        graph.run(case["question"], question_id=case["case_id"])
        broken = mutate(provider.generated[0], case["mutation"], case["faulty_text"])
        verdict = graph.verifier.verify(broken, graph.last_state["evidence"]).verdict
        flagged = verdict is not VerificationVerdict.PASS
        if case["should_detect"]: positives += 1; detected += flagged
        else: negatives += 1; false_positives += flagged
        details.append({"case_id": case["case_id"], "mutation": case["mutation"], "verdict": verdict.value, "correct": flagged == case["should_detect"]})
    return {"split": split, "case_count": len(cases), "positive_faults": positives,
            "verifier_catch_rate": detected / max(1, positives),
            "verifier_false_positive_rate": false_positives / max(1, negatives), "details": details}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--split", choices=("dev","test"), default="dev"); parser.add_argument("--output")
    args=parser.parse_args(); report=evaluate(args.split); text=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.output: Path(args.output).write_text(text)
    print(text,end="")


if __name__ == "__main__": main()
