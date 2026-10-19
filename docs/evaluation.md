# Evaluation and evidence scope

For the newly integrated development snapshot and its separate offline results,
see [candidate evaluation](release_candidate_evaluation.md). Historical results
below remain historical; they were not rerun or upgraded by that integration.

Results below describe specific checkpoints and runtimes. They must not be
combined into a single accuracy score. Historical frozen evaluations were not
rerun during publication preparation or release remediation.

## Planner and deterministic analytics

Regression tests cover company/metric/scope/period isolation, quarter versus
half-year grain, deterministic arithmetic, allowed calculations, reconciliation,
denominator safeguards and rejection behavior. The publication tree distributes
synthetic contract tests and numerical-demo regressions. Historical evaluation
definitions already present in the sanitized public base are retained unchanged,
including test questions and expected labels. Those published definitions cannot
be treated as secret, independent held-out data for future work. No new private
evaluation dataset or provider output is added. No new held-set result is claimed.

## Historical public evaluation fixtures: provenance and use

The following nine files are classified as **historical public evaluation
fixtures**, not confidential or unseen held-out benchmarks. All 111 cases and
their labels are retained byte-for-byte. Existing `_test` filenames and freeze
hashes preserve compatibility and the original evaluation record; they do not
make already-published cases independent unseen data for future claims.

| File | Cases | Fixture content and analytical reference |
|---|---:|---|
| [step4_test.jsonl](../evals/step4_test.jsonl) | 10 | Analytical questions, expected numerical/unit/operation/rejection labels; governed fact and calculation contracts |
| [step5_5_semantic_test.jsonl](../evals/step5_5_semantic_test.jsonl) | 8 | Retrieval questions, metadata filters and expected source/page/type labels |
| [step5_test.jsonl](../evals/step5_test.jsonl) | 15 | Retrieval questions and source-location expectations |
| [step6_test.jsonl](../evals/step6_test.jsonl) | 15 | Workflow questions and expected route/status labels |
| [step7_live_test.jsonl](../evals/step7_live_test.jsonl) | 5 | Historical live-workflow question definitions and expected route/status; no provider responses |
| [step7_siemens_agent_test.jsonl](../evals/step7_siemens_agent_test.jsonl) | 20 | Siemens workflow question definitions and expected route/status |
| [step7_siemens_retrieval_test.jsonl](../evals/step7_siemens_retrieval_test.jsonl) | 18 | Siemens retrieval questions, metadata filters and expected locations |
| [step7_verifier_test.jsonl](../evals/step7_verifier_test.jsonl) | 10 | Deliberately faulty short statements, mutation labels and detection expectations; not issuer assertions |
| [test.jsonl](../evals/test.jsonl) | 10 | Planner questions and expected company/metric/scope/period/status labels |

Repository provenance is the existing sanitized public commit
`79cd2a51776bbfbda2c5b98c596598211f6117a8`; these files predate the current additive
publication patch. This establishes repository custody, not a complete authorship
or permissions chain. Public-company reporting references are identified by the
[source manifest](../data/source_manifest.csv); numerical authority is separately
maintained in the [reviewed fact store](../data/normalized/facts.csv) and catalogs.
No imported third-party benchmark license or case-level permission document is
included in the fixture files.

### Rights boundary

Original project questions, fixture structure and annotations are subject to the
[project ownership notice](../LICENSE), to the extent they are original project
materials. That notice does not license underlying issuer content. Public access
to a report and prior publication in Git do not independently establish rights
to redistribute copied wording or other protected material.

The inspected fixtures contain short questions, identifiers, labels, numerical
expectations and deliberate fault statements—not raw reports, extracted corpora
or native provider transcripts. This content inventory is not a legal clearance.
The source manifest conservatively marks raw reports as
`rights_unclear_do_not_redistribute`; those raw files remain excluded. The
owner must establish authorship/permission or another applicable lawful basis
for any third-party content before redistribution. The project owner has confirmed
ownership or appropriate redistribution permission for these nine fixtures.
That confirmation is not an independent legal certification or a licence to
redistribute underlying reports. No blanket issuer grant is asserted. See the
official [Henkel terms](https://www.henkel.com/terms-of-use),
[Mercedes-Benz legal notice](https://group.mercedes-benz.com/provider/) and
[Siemens terms](https://www.siemens.com/en-us/terms-of-use/), together with any
report-specific conditions.

These fixtures may support separately authorized regression checks, but results
must be labelled public-fixture regression results—not new unseen performance.
No original benchmark is rerun during publication preparation. Future independent
evaluation requires separately controlled, unexposed cases and a new approved
protocol; the original checkpoint outcomes remain unchanged.

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

At the 1 October 2026 release checkpoint, 20 new targeted P1 regressions covered
numerical-prose contradictions and nearby variants, summary release, missing
structured values, unit relabeling, rate-limit abuse and the public-demo boundary.
They are included in the 288-test Python total, not an additional 20 independent
cases on top of it.

Eight deterministic-provider governance-bypass cases showed zero successful
authority compromises. These are controlled regression cases, not a universal
prompt-injection security guarantee. Historical seeded fault detection was
insufficient to detect the later prose escape; that defect is preserved as a
failure and addressed by the new tests and controlled renderer.

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

The already-public frozen definitions and version metadata are retained unchanged.
Original private runtime artifacts and provider traces are not redistributed.
The public summary
is transcribed from preserved historical reports, not a fresh held execution.

## Infrastructure and product

The release checkpoint passed 288 Python tests, 37 frontend tests, TypeScript
checking and the frontend production build. A clean public-safe copy built and
started in Docker, answered a numerical question with the explicitly fake
provider, intentionally refused a documentary definition and enforced quota
despite session rotation. The existing large visual-scene bundle warning remains.

Publication adds a separate credential-free public test selection and local CI
workflow. It does not claim that corpus-dependent integration tests are
reproducible without authorized local assets, or that newly prepared changes
have already passed hosted CI. Final packaging results are recorded in the
[publication checklist](publication_readiness.md).

## Offline continuation, 17 October 2026

The public-safe selection passed 154 tests locally and 154 in a freshly built
Docker image without external networking. That development frontend checkpoint passed 57
tests, TypeScript and the production build. These are software regressions,
not model-accuracy measurements or held evaluation reruns.

One previously authorized live documentary-completion review selected the
correct bounded repair option. Offline reconstruction confirmed the repaired
candidate was complete and deterministically verified, but residual interpretation
had no semantic approval. Its source-only final release remained PARTIAL.
Subsequent offline changes repaired withheld-ID tracking, documentary reason
labelling, fixture-state propagation and partial scoring, without relaxing review
or final verification. The historical PARTIAL result was not rewritten as PASS.
No live provider call occurred during this offline continuation; broader
fallback/end-to-end validation and human acceptance remain pending.

## Public compatibility checkpoint, 18 October 2026

The complete additive publication overlay passed 194 public Python tests locally
and the same 194 in Docker, including 27 compatibility checks. The reused public
frontend passed 101 tests plus production and recorded-demo builds. These counts
supersede neither historical held outcomes nor the separate private integration
results, and repeated environment runs are not additional independent cases.

## Interpretation boundaries

Functional correctness, retrieval relevance, release safety, live-provider
reliability and product usability are distinct. Remaining semantic coverage,
UI acceptance, authentication/tenant isolation and deployment limits remain
visible in [limitations](limitations.md).
