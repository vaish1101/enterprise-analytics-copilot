# Evaluation and evidence scope

Results below describe specific checkpoints and runtimes. They must not be
combined into a single accuracy score. Historical frozen evaluations were not
rerun during publication preparation or release remediation.

## Planner and deterministic analytics

Regression tests cover company/metric/scope/period isolation, quarter versus
half-year grain, deterministic arithmetic, allowed calculations, reconciliation,
denominator safeguards and rejection behavior. Public development evaluators
and their cases remain in `scripts/` and `evals/`; they are not general reasoning
benchmarks. No new held-set result is claimed.

## Retrieval

The frozen initial Siemens retrieval evaluation covered 18 questions, including
12 positive retrieval cases. Its preserved report recorded Hit@1/3/5,
Recall@5 and MRR at 100%, with citation precision 93.75%. The positive-case
denominator and filtering/annotation contract matter; this is not a claim that
retrieval is universally perfect. These results require the original authorized
corpus and frozen configuration, which are not distributed in the public demo.

The current full-local design is metadata-first MiniLM dense top-five retrieval;
BM25/RRF measurements belong to their diagnostic checkpoints. Public CI does
not download reports or manufacture a replacement corpus to rerun these results.

## Verifier and security

The public regression selection covers numerical-prose contradictions and nearby
variants, summary release, unit binding, rate-limit abuse and public-demo
boundaries. Frontend regressions reject missing or inconsistent verification
and exercise recorded-mode isolation from API and provider calls.

Eight deterministic-provider governance-bypass cases showed zero successful
authority compromises. These are controlled regression cases, not a universal
prompt-injection security guarantee.

## End-to-end and held-out results

| Checkpoint | Runtime/provider | Scope | Preserved result and failure |
|---|---|---|---|
| Initial Siemens generalization | Deterministic provider | 20 agent/workflow cases | 18/20 expected outcomes; two valid Mobility requests conservatively refused; tool selection 80% |
| Live-provider held checkpoint, 28 September 2026 | OpenAI `gpt-6-luna`, structured synthesis | 5 questions, run once | 4/5 expected outcomes; one bounded provider/runtime failure |
| Live-provider development checkpoint | Same historical live-provider configuration | 8 questions | 7/8 grounded task outcomes; one failed expected outcome; supported subsets and refusal retained |

The historical reports recorded numerical/citation/provenance safety at 100%
among released outcomes. That conditional denominator does not mean every
question succeeded, nor does it certify the remediated current implementation.
Fake-provider diagnostics are not live token, latency or cost measurements.
Failed-attempt usage was unavailable in the live held failure, so historical cost
totals are not complete spending estimates. No current pricing claim is made.

Frozen definitions and version metadata remain unchanged in
`evals/step7_siemens_agent_test.jsonl`, `evals/step7_siemens_retrieval_test.jsonl`,
`evals/step7_live_test.jsonl` and `config/step7_1_live_freeze.json`. Original full
runtime artifacts are retained privately, not redistributed. The public summary
is transcribed from preserved historical reports, not a fresh held execution.

## Infrastructure and product

The sanitized public selection passed 151 Python tests and the integrated UI
passed 101 frontend tests on 1 October 2026. TypeScript checking and the
recorded-demo production build passed. These are regression results, not held
accuracy measurements. The visual-scene build retains a large-chunk warning.

Publication adds a separate credential-free public test selection and local CI
workflow. It does not claim that corpus-dependent integration tests are
reproducible without authorized local assets, or that GitHub-hosted CI has run
before a remote repository exists. The public frontend replays recorded outputs;
it does not run the held evaluation or live agents in the browser.

## Interpretation

Functional correctness, retrieval relevance, release safety, live-provider
reliability and product usability are distinct. Remaining semantic coverage,
UI acceptance, authentication/tenant isolation and deployment limits remain
visible in [limitations](limitations.md).
