# Enterprise Analytics Copilot

**Governed AI for KPI analysis, variance explanation, reporting context, and decision support.**

A governed analytics workflow that combines reported figures, deterministic calculations, reporting evidence and independent checks. Ask what changed, inspect what supports the answer, and see what cannot be concluded.

Ask a business question. See the analysis behind the answer.

![Enterprise Analytics Copilot, approved light-mode interface with recorded-demo disclosure](assets/screenshots/product-overview.png)

[Architecture](docs/architecture.md) · [Evaluation](docs/evaluation.md) · [Reproduction](docs/reproduction.md) · [Data and rights](docs/data_sources.md)

[Try the interactive demo](https://enterprise-analytics-copilot.vercel.app/). Explore validated recorded examples in the web app. This is not a video or live AI.

> Two credential-free demonstrations are available: a **frontend-only recorded replay** and a **local numerical Docker workflow** using a deterministic template provider. Neither makes live AI calls. The full authorized backend adds documentary retrieval and structured model synthesis; its publisher-owned corpus and runtime assets are not distributed.

## Business problem

Investigating a KPI usually means moving between dashboards, spreadsheets, metric definitions and company reports. The figure, its comparison period and management's explanation may sit in different places, and a plausible explanation is not necessarily supported.

This project brings that investigation into one bounded workflow: identify the metric and scope, execute the appropriate numerical analysis, assemble available evidence, and release only supported findings or a clear boundary.

## What it does

| Business question | Supported workflow |
|---|---|
| What was the reported figure? | Governed lookup with company, scope, period, unit and fact lineage |
| How much did it change? | Deterministic period comparison, subject to metric policy |
| What contributed to the change? | Reviewed reported decompositions, without inventing unavailable splits |
| How is this metric defined? | Filtered documentary retrieval in the full local environment |
| What did management report? | Source-supported context, visibly separate from causal proof |
| What evidence supports the answer? | Inspectable provenance and available source references |

Support depends on catalog and dataset coverage. Ambiguous requests ask for clarification; unsupported or insufficiently evidenced requests refuse.

## Example investigation

**“What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?”**

At the reviewed source checkpoint, Cars adjusted EBIT decreased by **EUR 319 million**, from EUR 1,228 million in Q2 2025 to EUR 909 million in Q2 2026. Management's largest negative bridge contribution was the **combined** “Volume / structure / net pricing” category, at EUR −602 million.

| Figure | EUR million |
|---|---:|
| Q2 2025 adjusted EBIT | 1,228 |
| Combined volume / structure / net pricing contribution | −602 |
| Q2 2026 adjusted EBIT | 909 |

The complete seven-component bridge reconciles to 909. The combined category cannot be split into price, volume or mix effects, and management attribution is not causal identification. [Inspect the source mapping](docs/mercedes_xlsx_mapping.md).

The frontend includes a clearly labelled recorded illustration of this investigation. The local numerical Docker runtime intentionally refuses documentary explanations without the excluded corpus. Neither demonstration claims to run live documentary retrieval.

## How it works

![Question-to-supported-answer workflow](assets/architecture/high-level.svg)

A deterministic, catalog-grounded planner selects bounded tools. Numerical authority stays with governed facts and deterministic calculations, not the model. Structured synthesis proposes claims; independent verification checks their data, lineage and release contract. Outcomes include a released answer, a supported subset, clarification or refusal.

The workflow separates routing, analytics, retrieval, synthesis and verification into logical roles. It is not an autonomous analyst workforce. [Technical architecture](docs/architecture.md) · [Methodology](docs/methodology.md)

## Evidence and verification

- Company-specific metrics retain their scope, period, grain, units and evidence expectations.
- Reported facts, calculations and management attribution have distinct provenance.
- The full local retrieval path filters metadata before MiniLM dense retrieval through PostgreSQL/pgvector, with top-five results and an HNSW index.
- Numerical prose is checked conservatively; released numerical text is bound to verified structured fields. Unchecked draft summaries are not released.
- Missing or inconsistent frontend verification payloads fail closed, even after HTTP success.

Verification is a bounded contract check, not a universal semantic truth guarantee. Reconciliation does not prove that two metrics mean the same thing. [Provenance and verification](docs/provenance_and_verification.md)

## Validation snapshot

These measurements are different kinds of evidence, not one blended accuracy score.

| Evidence | Scoped result |
|---|---|
| Public regression suite, 1 October 2026 | 151 Python tests; 101 frontend tests; TypeScript and recorded-demo production build passed |
| Governance-bypass regression | 8 cases; no successful authority compromise under the deterministic test provider |
| Frozen Siemens initial evaluation | 18/20 task outcomes correct; two valid questions refused; deterministic provider |
| Frozen live-provider held evaluation | 4/5 expected outcomes; one bounded provider/runtime failure; OpenAI synthesis |
| Public-safe Docker | Numerical workflow, no bundled corpus or credentials; see reproduction instructions |

The historical held evaluations describe their original frozen implementations, not the current safety patch. They were not rerun. Tests do not establish general reasoning accuracy or enterprise production readiness. [Evaluation scope and failures](docs/evaluation.md)

## Demo datasets

Mercedes-Benz, Henkel and Siemens are used only as public-reporting demo datasets. No affiliation, sponsorship, partnership or endorsement is implied.

The repository ships reviewed derived numerical facts, metric contracts and source metadata. Raw reports, workbooks, full extracted text, embeddings, private indexes and runtime stores are excluded. [Source metadata and rights](docs/data_sources.md)

## Demonstration

The interface includes light/dark themes, English/German controls, a 3D workflow illustration, source inspection and explicit clarification/refusal states. Analytical wording remains in the source language.

[Dark theme](assets/screenshots/product-overview-dark.png) · [Supported figure](assets/screenshots/supported-analysis.png) · [Source inspector](assets/screenshots/evidence-inspector.png) · [Disclosure boundary](assets/screenshots/governed-refusal.png)

The frontend-only mode replays selected validated examples and the recorded Mercedes investigation. Other questions are refused rather than sent to a backend or model. Definitions and commentary that need the unavailable corpus remain bounded. History is page-local; there is no remote session persistence in this mode.

```bash
cd frontend
npm ci
npm run build:demo
npm run preview
```

The [public recorded demo](https://enterprise-analytics-copilot.vercel.app/) is hosted on Vercel. The README does not depend on a video recording.

## Technology

| Layer | Implementation |
|---|---|
| Product interface | React, TypeScript, Vite; Three.js and GSAP in the current visual implementation |
| API and contracts | Python, FastAPI, Pydantic |
| Numerical analytics | Governed metric catalog, Decimal calculations and controlled reconciliation |
| Synthesis and orchestration | LangGraph; OpenAI Structured Outputs in the full local environment |
| Documentary retrieval | sentence-transformers/MiniLM, PostgreSQL, pgvector, HNSW |
| Persistence and infrastructure | SQLite or PostgreSQL checkpoint/session stores; Docker |
| Validation | pytest, Vitest, Testing Library, TypeScript; public-safe CI workflow |

## Run the public demo

With Docker and Docker Compose installed, from the repository root:

```bash
docker compose -f docker-compose.public.yml up --build -d
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
```

Open `http://localhost:8000` and try **“What were Henkel H1 2026 sales?”** No `.env`, API key or documentary corpus is needed. A definition question intentionally refuses.

Stop it with `docker compose -f docker-compose.public.yml down`. Port 8000 must be free. The first build downloads dependencies; “credential-free” does not mean the first build is offline.

[Public reproduction and tests](docs/reproduction.md) · [Full-local prerequisites and deployment boundaries](docs/deployment.md) · [Empty configuration template](.env.example)

## Repository guide

```text
src/          planning, analytics, retrieval, orchestration, API and contracts
frontend/     product interface and frontend tests
config/       governed metric/scope/period/source contracts and frozen metadata
data/         reviewed derived figures and public-safe source metadata
tests/        unit, rejection, fault and integration regressions
evals/        development cases and preserved frozen evaluation definitions
scripts/      acquisition, validation, evaluation and public-safety tooling
docs/         architecture, methodology, evaluation, limits and reproduction
assets/       architecture visuals; approved product/demo asset slots
```

## Limitations and public safety

Coverage is bounded, metric semantics remain company-specific, and management attribution is not causal proof. There is no unrestricted SQL/Python execution, forecasting contract, arbitrary onboarding through prompts, or validated enterprise authentication/tenant boundary. Anonymous rate limits are process-local; multiple instances require shared gateway enforcement.

The public Docker demo does not reproduce private documentary retrieval. The hosted interface is a recorded replay, not live AI; no production scalability claim is made. [Full limitations](docs/limitations.md)

Secrets, local runtime state, publisher-owned corpora and internal development reports are not distributed. The optional bounded-agent experiment is disabled by default and is not the basis of production claims.

## Ownership and usage

Designed and developed by Vaishnavi Iyer as an independent portfolio project.

© 2026 Vaishnavi Iyer. All rights reserved.

This repository is provided for portfolio, educational and evaluation purposes. All rights reserved unless otherwise stated.

No open-source license or broad reuse rights are granted. See the [ownership and usage terms](LICENSE). Third-party reports, source material, fonts and dependencies remain subject to their respective owners' rights and terms. [Third-party notices](THIRD_PARTY_NOTICES.md).

**Vaishnavi Iyer** · [LinkedIn](https://www.linkedin.com/in/vaishnavi-iyer-60b9141b1/)
