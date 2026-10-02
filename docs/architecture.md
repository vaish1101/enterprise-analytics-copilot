# Architecture

The planner owns tool selection. Governed data and deterministic calculations
own numbers. Synthesis proposes structured claims; verification and release
logic decide what may be shown. This is a bounded analytical workflow, not a
swarm of autonomous agents.

![High-level workflow](../assets/architecture/high-level.svg)

## Technical view

![Technical architecture](../assets/architecture/technical.svg)

Both diagrams are editable project visuals. They describe the backend contract,
not a live trace in the frontend-only recorded demonstration.

| Component | Responsibility | Implementation |
|---|---|---|
| React interface | Question intake, result/evidence presentation, response validation | `frontend/src/` |
| FastAPI | Request validation, anonymous quota, bounded request handling, sessions | `src/api/` |
| Deterministic planner/router | Company, catalog metric, operation, scope, period and supported route | `src/planning/` |
| Analytics | Fact lookup, Decimal calculations, decomposition and controlled reconciliation | `src/analytics/` and `src/validation/` |
| Knowledge/retrieval | Metadata filtering and governed top-five documentary evidence | `src/retrieval/` |
| Evidence assembly | Separate numerical and documentary authority; retain selected lineage | `src/orchestration/graph.py` |
| Structured synthesis | Schema-constrained draft; one bounded revision when applicable | `src/llm/` and `src/orchestration/models.py` |
| Independent verifier | Number/unit/identity/lineage/provenance/citation checks and conservative numerical prose checks | `src/orchestration/verifier.py` |
| Release boundary | Supported claims only; bound numeric rendering; clarification/refusal when required | `src/orchestration/graph.py` |

Original role templates in `prompts/` are published project source, not private
provider transcripts or hidden reasoning. Untrusted documentary content cannot
authorize tools or replace governed instructions. No chain-of-thought is exposed.

## Data and persistence

The public numerical authority is the reviewed CSV fact store, validated against
the metric catalog and Pydantic contracts. The normalized SQL schema defines and
tests the corresponding data contract; it is not a claim that every public
numeric request executes SQL against PostgreSQL.

Full-local semantic retrieval uses `sentence-transformers/all-MiniLM-L6-v2`,
metadata-first filtering, top-k five and cosine similarity. The wired Compose
runtime uses PostgreSQL/pgvector with HNSW; an authorized local MiniLM cosine
store is also supported. BM25 and RRF are diagnostics/fallback implementations,
not the current default semantic retrieval claim.

Checkpoint/session stores use SQLite in the numerical demo or PostgreSQL in the
private Compose topology. Their contents are runtime state and are not shipped.

## Execution modes

| Mode | Numerical data | Documentary data | Synthesis |
|---|---|---|---|
| Public Docker demo | Committed reviewed derived facts | Disabled; documentary questions refuse | Deterministic fake/template provider |
| Authorized full local | Same governed contracts | Locally acquired corpus and model cache, or pgvector | Configured OpenAI structured provider |
| Frontend-only recorded demonstration | Validated recorded outputs | Source metadata and citations in the illustration, no corpus | Recorded/template wording, no model calls |

The full local environment is not reproduced by a clone alone. External LLM
calls are outside numerical authority and outside public CI. [Deployment and
proxy assumptions](deployment.md) · [Reproduction](reproduction.md)

## Optional bounded-agent experiment

`src/bounded_agents/` contains an opt-in research path with model-backed bounded
action selection, provider budgets and a deterministic final release gate.
It remains experimental and disabled by default. Its development behavior is
not covered by the historical governed-workflow evaluation results or the
public recorded demonstration; no production multi-agent claim is made.
