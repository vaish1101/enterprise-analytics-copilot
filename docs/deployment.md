# Deployment boundaries

## Validated local public demo

`docker-compose.public.yml` builds the `public-demo` target, serves React through
FastAPI and binds localhost only. The mode uses committed numerical facts, a
deterministic template provider and local SQLite persistence; documentary
retrieval is explicitly disabled. No credentials or private source assets are
needed. It is a local portfolio demonstration, not a hosted production service.

## Authorized full-local stack

The retained `docker-compose.yml` and `docker-compose.pgvector.yml` describe a
separately configured PostgreSQL/pgvector stack and evidence loader. Its private
corpus, model cache and runtime stores are not distributed. Source interfaces
and topology are included for engineering review, but a public clone alone does
not reproduce that private stack. Optional semantic
dependencies require an authorized local setup. No private corpora, embeddings
or raw reports are baked into the public image.

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
private topology requires missing values explicitly rather than inventing
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

## Planned, not deployed

A live frontend-to-FastAPI connection, managed PostgreSQL/pgvector and an external
provider are possible future deployment choices, not existing hosted assets.
The old host-specific template is retained privately because it is not validated
for the current public/private target distinction. The existing Vercel URL hosts
only the recorded frontend replay; no live AI backend, Pages site or public
container registry image is claimed.

Before any Internet deployment, review authentication/tenant/session access,
TLS/origins, secrets, database extension/index availability, corpus rights,
anonymous/shared quotas, cancellation/backpressure, provider limits and actual
cost telemetry. Then smoke-test the real URL before adding a Live Demo link.

[Reproduction](reproduction.md) · [Limitations](limitations.md)
