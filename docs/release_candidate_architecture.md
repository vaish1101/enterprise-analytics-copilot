# Implemented bounded-agent candidate

The validated default is unchanged. `src/bounded_agents/experimental_app.py` explicitly composes the experimental graph with the existing FastAPI service using a fresh request-scoped graph. It accepts application-owned provider/retriever factories; clients cannot choose an arm, tool or permission. It rejects production/public-demo mode and permits synthetic sources only in test mode. C is the four-role candidate; B is an evaluation baseline.

## Data flow and shared state

Question → deterministic planner/router → bounded investigation → analytics/retrieval results → evidence bundle → synthesis → selective semantic review → deterministic verification → FULL/PARTIAL/WITHHELD or clarification.

`runtime.py::_build` creates the LangGraph state machine. `SpikeState` extends typed graph state; node updates carry plan, route, analytics, retrieval, evidence, draft, critic and verification records. Investigation invokes analytics and evidence roles conditionally; they are not separate independent supervisors. Revision returns to review and verification. Graph topology and final numerical verification are unchanged by the evidence correction.

## Real decision points

- `runtime.py::_investigate` / `_execute_action`: an admitted `analytics.choose` structured call selects an approved diagnostic action. Python validates it and executes it; canonical analytics remains mandatory. Resolved tasks and ranking can bypass the model decision.
- `_evidence` / `_search`: an admitted `evidence.choose` call selects from actual backend capabilities, with one precommitted different strategy only where bounded coverage rules permit it. Scope and source guards validate tool results.
- `_generate`: structured synthesis selects approved evidence/context. Canonical numerical claims and exact-source quotations remain application-owned. Missing admitted explanation can skip synthesis and use the governed numerical subset.
- `_critic`: selective semantic review is model-backed when required and admitted. Its typed decisions affect bounded repair/removal/refusal. Extractive supported paths can skip semantic review; not every query invokes all roles.
- `_verify` / `_finalize`: deterministic verification controls exact released claims; model approval cannot override arithmetic, lineage, scope or source checks.

## Diagnostic reliability integration

`diagnostic_policy.py` is the frozen passage policy moved into the application package. Its B/C subclasses apply the same constraints. It distinguishes canonical integrity/authenticity classification, metadata scope, local question relevance, explanation admission and actual answer support. Source IDs, hashes and character spans are preserved; canonical sources are not rewritten. Definition-only, irrelevant commentary, forecast-only and numeric-only evidence do not imply a historical explanation.

The retriever remains metadata-first dense pgvector/top-five in the full authorized path. Bounded type preference admits actual explanatory prose inside mixed TABLE containers. A request-local exact-query cache revalidates raw results, does not widen permissions and does not share state between users. No reranker, unrestricted search or new embedding model was introduced.

Missing documentary support yields only freshly verified numerical PARTIAL output where useful; otherwise withholding. Growth-rate change without a comparison period remains unresolved even if current-period commentary exists. Deterministic one-attempt source completion is not a model retry or evidence of semantic-agent contribution.

## Permissions, limits and operational boundaries

Tool authorizers enforce resolved plans and approved action/strategy enums. Model outputs cannot execute arbitrary code, SQL or web instructions. Source text is data, not authority to change system permissions. Source integrity and deterministic verification are not universal semantic truth checks.

The integrated factory uses the existing six-dispatch role/request budget, zero retries, four-tool/two-retrieval comparison envelope and existing deadline reserves. Budget admission does not mean every slot is used. Timeout does not guarantee cancellation of upstream billed work; unknown outcomes require conservative spend reservation in an approved live runner.

Local API rate limiting and process locks are not distributed production quotas. Session IDs are not authentication or tenant authorization. External deployment requires additional boundary review and approval; no public multi-user security claim is made.

## Evidence interpretation

Offline traces demonstrate software paths using explicitly scripted decisions; they do not prove model judgment. Historical live reviewer cases remain separate. Neither passing fixtures nor matching pgvector IDs establishes multi-agent superiority. Retain the candidate for honest examination without inventing autonomy.
