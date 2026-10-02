"""Opt-in paid paired development run; never loads held cases/private passages.

Requires explicit model, verified worst-case prices and a single-run spending cap.
Produces observations for rubric review, not an automatic marketing score.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_bounded_agents_dev import synthetic_units
from src.bounded_agents import create_workflow
from src.bounded_agents.models import AgentBudgetState
from src.bounded_agents.provider import BudgetedOpenAIProvider, SpendLedger
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.embeddings import LocalHashEmbeddingProvider

QUESTIONS = (
    "Give the governed Henkel group sales figure for H1 2026.",
    "Calculate the change in Henkel group sales from H1 2025 to H1 2026.",
    "What helped Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What hurt Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What had the biggest impact on Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "Explain the definition of Henkel organic sales growth.",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly enable paid API calls")
    parser.add_argument("--model")
    parser.add_argument("--max-usd")
    parser.add_argument("--input-rate", help="Verified worst-case USD per million input tokens")
    parser.add_argument("--output-rate", help="Verified USD per million output/reasoning tokens")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status":"NOT_RUN", "questions":QUESTIONS,
            "requirements":"explicit model, USD cap, verified rates, API key and --execute",
            "evidence":"synthetic development passages only; no held set"}, indent=2))
        return
    if not all((args.model, args.max_usd, args.input_rate, args.output_rate)):
        parser.error("Paid execution requires explicit model, spending cap and verified prices")
    ledger = SpendLedger(args.max_usd)
    rows = []
    for index, question in enumerate(QUESTIONS):
        # Alternate order to reduce systematic warm-up/order bias. One pass is
        # exploratory, not statistically reliable latency evidence.
        modes = ("governed_v1", "bounded_agents_v2") if index % 2 == 0 else ("bounded_agents_v2", "governed_v1")
        for mode in modes:
            if ledger.blocked or ledger.committed_usd >= ledger.max_usd:
                break
            provider = BudgetedOpenAIProvider(model=args.model, input_rate=args.input_rate,
                output_rate=args.output_rate, ledger=ledger, limits=AgentBudgetState(max_retries=0))
            retriever = GovernedRetriever(synthetic_units(), root=ROOT,
                embedding_provider=LocalHashEmbeddingProvider())
            options = {"budgets":AgentBudgetState(max_retries=0)} if mode == "bounded_agents_v2" else {"max_provider_attempts":1}
            workflow = create_workflow(ROOT, mode=mode, provider=provider, retriever=retriever, **options)
            started = time.monotonic()
            brief = workflow.run(question, question_id=f"fresh_comparison_{index}_{mode}")
            traces = getattr(workflow, "agent_trace", ())
            rows.append({"case":index, "mode":mode, "question":question,
                "status":brief.status.value, "answer":brief.answer,
                "verification":brief.verification.model_dump(mode="json") if brief.verification else None,
                "attempts":provider.calls,
                "generation_requests":len(provider.records),
                "input_tokens":sum(x.get("input_tokens", 0) for x in provider.records),
                "output_tokens":sum(x.get("output_tokens", 0) for x in provider.records),
                "cost_usd_known":str(sum((Decimal(x.get("actual_usd", "0")) for x in provider.records), start=Decimal("0"))),
                "provider_records":provider.records,
                "provider_preflights":provider.preflights,
                "provider_failures":provider.failures,
                "workflow_errors":[x.error_code for x in brief.trace if x.error_code],
                "latency_ms":round((time.monotonic()-started)*1000, 2),
                "actions":[x.action.value for x in getattr(workflow, "observations", ())],
                "trace":[x.model_dump(mode="json") for x in traces],
                "reconciliation":[x.passed for obs in getattr(workflow, "observations", ()) for x in obs.result.reconciliation_results],
                "rubric_review":{"task_correct":None, "useful_investigation":None,
                    "unnecessary_calls":None, "critic_useful_intervention":None,
                    "critic_false_positive":None}, "fallback":False})
    print(json.dumps({"status":"REQUIRES_RUBRIC_REVIEW", "provider":"openai",
        "model":args.model, "single_run_cap_usd":str(ledger.max_usd),
        "known_plus_unknown_reserved_usd":str(ledger.committed_usd),
        "evidence":"synthetic development passages; not issuer quotations",
        "historical_evaluation_claims_apply":False, "promotion":False, "rows":rows}, indent=2))


if __name__ == "__main__":
    main()
