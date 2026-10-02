# Deployment boundaries

## Validated local public demo

`docker-compose.public.yml` builds the `public-demo` target, serves React through
FastAPI and binds localhost only. The mode uses committed numerical facts, a
deterministic template provider and local SQLite persistence; documentary
retrieval is explicitly disabled. No credentials or private source assets are
needed. It is a local portfolio demonstration, not a hosted production service.

## Authorized full-local stack

`docker-compose.yml` explicitly builds `private-runtime`, with a PostgreSQL/
pgvector service and a one-shot evidence loader. The loader generates its schema
from committed DDL; no ignored generated SQL is mounted. API/loader receive
authorized corpus and model-cache mounts read-only. Neither target bakes private
corpora, embeddings or raw reports into the image.

Before this private stack can start, supply local-only configuration through the
variables already supported by the code/Compose definitions:

| Group | Names |
|---|---|
| Provider | `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` |
| Optional cost accounting | `LLM_INPUT_COST_PER_MILLION`, `LLM_OUTPUT_COST_PER_MILLION` |
| Database and persistence | `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `CHECKPOINT_BACKEND`, `CHECKPOINT_URI`, `SESSION_DATABASE_URL`, `SESSION_DB_PATH` |
| Application | `APP_MODE`, `PUBLIC_DEMO`, `RETRIEVAL_BACKEND`, `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `MAX_QUESTION_LENGTH`, `APP_REQUEST_TIMEOUT_SECONDS`, `LOG_LEVEL`, `PORT` |

Database connections must refer to the intended private Compose service/network.
No credential-bearing connection example or default password is published. The
private Compose file requires missing values explicitly rather than inventing
usable defaults. Store real values only in ignored local configuration or a
secret manager, never in Git, screenshots or public logs.

## Anonymous quotas and proxy trust

The quota is tied to the observed transport peer, not header/body session IDs.
Salted peer hashes live only in memory and inactive buckets expire. Locking
enforces atomic limits; 10,000 peer buckets bound memory and fail closed.
NAT clients share quota and process restarts reset it. Quotas are not shared
between workers or replicas.

Docker disables Uvicorn proxy-header interpretation. A spoofed forwarded address
cannot choose a fresh quota identity. Behind a proxy, sharing the proxy peer
quota is conservative. Enable forwarding only with a trusted allowlist and
sanitized headers plus gateway enforcement. Multi-instance exposure requires
shared gateway limits, spending controls and capacity/backpressure review.

## Frontend-only recorded deployment preparation

The root `vercel.json` installs the frontend dependencies, runs `build:demo` and
serves `frontend/dist` with SPA routing. Select the repository root, not the
frontend subdirectory. No backend, model key, database or provider configuration
is required. Public mode performs exact-question fixture replay only and refuses
other questions; it never falls back to a network request. Result and workflow
views identify recorded outputs. The local API-connected build uses `npm run
build` instead and is a separate mode.

Confirm the intended account/project and free plan before deployment. No hosted
deployment is claimed by these preparation instructions. Review the actual URL,
assets, themes, language, source links and refusal paths before advertising it.
See [Vercel build configuration](https://vercel.com/docs/builds/configure-a-build).

## Authorized backend hosting boundary

A separated frontend host, FastAPI service, managed PostgreSQL/pgvector and an
external provider are possible future topology choices, not deployed assets.
The old host-specific template is retained privately because it is not validated
for the current public/private target distinction. No URL, release, Pages site
or registry image has been published.

Before any Internet deployment, review authentication/tenant/session access,
TLS/origins, secrets, database extension/index availability, corpus rights,
anonymous/shared quotas, cancellation/backpressure, provider limits and actual
cost telemetry. Then smoke-test the real URL before adding a Live Demo link.

[Reproduction](reproduction.md) · [Limitations](limitations.md)
