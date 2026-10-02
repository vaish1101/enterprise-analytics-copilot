# syntax=docker/dockerfile:1.7
FROM node:26-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build \
    && mkdir -p dist/assets/licenses \
    && cp node_modules/@fontsource-variable/geist/LICENSE dist/assets/licenses/geist.txt \
    && cp node_modules/@fontsource-variable/geist-mono/LICENSE dist/assets/licenses/geist-mono.txt \
    && cp node_modules/@fontsource/instrument-serif/LICENSE dist/assets/licenses/instrument-serif.txt

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements-step6.txt requirements-step5-semantic.txt requirements-step8.txt ./
# Use the CPU wheel explicitly. The PyPI Linux wheel can pull multi-gigabyte CUDA
# libraries even though this service runs the locked MiniLM encoder on CPU.
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-step8.txt
COPY config/ config/
COPY data/source_manifest.csv data/source_manifest.csv
COPY data/normalized/ data/normalized/
COPY prompts/ prompts/
COPY src/ src/
COPY LICENSE THIRD_PARTY_NOTICES.md ./
COPY scripts/load_pgvector_evidence.py scripts/load_pgvector_evidence.py
COPY scripts/evaluate_step8_6a_retrieval_parity.py scripts/evaluate_step8_6a_retrieval_parity.py
COPY evals/step5_5_semantic_dev.jsonl evals/step5_5_semantic_dev.jsonl
COPY --from=frontend /build/frontend/dist frontend/dist
RUN mkdir -p data/checkpoints && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT} --no-proxy-headers"]

# Authorized local corpora/model caches are mounted, never baked into an image.
FROM base AS private-runtime

# Default clean-clone target: derived numbers + fake provider, no raw/corpus assets.
FROM base AS public-demo
ENV APP_MODE=demo PUBLIC_DEMO=1 RETRIEVAL_BACKEND=local
