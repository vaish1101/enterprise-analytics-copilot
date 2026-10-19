# Public reproduction

## What the clone includes

Source, tests, catalog/schema contracts, reviewed derived numerical facts,
source metadata, curated documentation and original architecture visuals.
It does not include raw reports/workbooks, full extracted text, model caches,
embeddings, vector dumps, checkpoint/session state or secrets.

The sanitized public repository is
[enterprise-analytics-copilot](https://github.com/vaish1101/enterprise-analytics-copilot).
The existing Vercel demonstration is a recorded frontend replay, not a hosted
live AI backend. The source also includes an opt-in experimental four-role
workflow; that workflow is not selected by public-demo startup.

## Docker-first numerical demo

Prerequisites: Docker with Compose, registry/package network access for the first
build, and an available localhost port 8000. No `.env` or API key is required.
From the repository root:

```bash
docker compose -f docker-compose.public.yml config --quiet
docker compose -f docker-compose.public.yml up --build -d
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
```

Open `http://localhost:8000`. The React production build is served by FastAPI.
Try “What were Henkel H1 2026 sales?” The governed value is EUR 10,348 million;
provider metadata identifies the deterministic fake/template provider. This is
not live synthesis. “How does Henkel define organic sales growth?” intentionally
refuses because the documentary corpus is not distributed.

```bash
docker compose -f docker-compose.public.yml down
```

The default Dockerfile target is also `public-demo`. `.dockerignore` excludes
private archives and local retrieval/raw/runtime assets. A cached dependency
layer does not change the public input boundary.

## Credential-free public tests

The public suite selection is recorded in `config/public_tests.json`. It covers
contracts, analytics/planning, acquisition rejection logic, public-mode API
boundaries and standalone release controls. It does not execute held evaluators
or depend on publisher files/private corpora.
The runner forces test-mode/memory configuration and removes database/provider
credentials from the child environment. Acquisition tests create controlled
temporary raw-path fixtures, so run the suite in a writable checkout or disposable
copy; API startup itself uses memory rather than a developer database.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-public.txt
.venv/bin/python scripts/test_public.py
.venv/bin/python scripts/public_release_check.py
cd frontend
npm ci
npm test
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

Use Python 3.13 and Node 26 for parity with the Docker/CI definitions. `.env.example`
contains variable names and empty placeholders only. Do not load every blank
optional variable into a numerical-demo process; its image defaults are sufficient.

## Full authorized local environment

Only a separately authorized environment can acquire the official sources and
build the private corpus/model cache. Do not confuse those steps with public
reproduction. Acquisition validates listed hosts, media/signatures and checksums
inside the ignored raw boundary; rights remain with the publishers. Do not rerun
frozen held evaluations as a setup step. [Sources](data_sources.md) ·
[Private runtime prerequisites](deployment.md)

The full private development suite requires authorized assets and is not fully
reproducible from this public tree. Previously public evaluation definitions
remain unchanged for historical continuity; do not execute frozen held sets. The
public tests here are self-contained and do not require those assets. Historical
held results are preserved privately, not outputs a stranger must regenerate.

The full-local test total includes frozen development/intervention fixtures and
is not the public suite count. Use the explicit public selection above. Frontend
v2 response tests use labelled synthetic wire fixtures, not private Python fixture
generators or evidence of live end-to-end success. Do not copy private fixtures
or run held evaluators to complete setup. Bounded-agent and repair-option features
remain opt-in development paths, not a change to the numerical-demo default.
