.PHONY: api ui test test-public public-check demo demo-stop build

demo:
	docker compose -f docker-compose.public.yml up --build -d

demo-stop:
	docker compose -f docker-compose.public.yml down

test-public:
	python scripts/test_public.py

public-check:
	python scripts/public_release_check.py --history

api:
	.venv/bin/uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000

ui:
	cd frontend && npm run dev

test:
	.venv/bin/pytest -q
	cd frontend && npm test

build:
	cd frontend && npm run build
