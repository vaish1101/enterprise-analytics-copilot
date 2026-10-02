# Public reproduction

## What the clone includes

Source, tests, catalog/schema contracts, reviewed derived numerical facts,
source metadata, curated documentation and original architecture visuals.
It does not include raw reports/workbooks, full extracted text, model caches,
embeddings, vector dumps, checkpoint/session state or secrets.

A remote repository has not been created. Until a reviewed remote URL exists,
use a local checkout; no invented clone URL or live-demo link is provided.

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
npm run build:demo
npm run preview
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

The full relevant local regression command is `.venv/bin/python -m pytest tests`;
some tests require already acquired authorized assets. Missing such assets is
not a public Docker defect. Historical held results are preserved records,
not outputs a stranger must regenerate.
