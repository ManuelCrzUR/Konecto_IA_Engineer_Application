.DEFAULT_GOAL := help
.PHONY: help up down reset logs test eval chat ingest db recovery

# Host port for the API. Read from the shell env first, then from .env, then 8000.
# (Make does not read .env by itself; Compose does, for the ${API_PORT} substitution.)
API_PORT ?= $(or $(shell sed -n 's/^API_PORT=//p' .env 2>/dev/null | tail -1),8000)

help: ## Show this help (default target)
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start the stack, then wait until the API is healthy (API_PORT=8001 to change the port)
	docker compose up -d --build
	@echo "Waiting for the API to become healthy (up to 120 s)..."
	@cid=$$(docker compose ps -q api); \
	i=0; status=starting; \
	while [ $$i -lt 60 ]; do \
		status=$$(docker inspect --format '{{.State.Health.Status}}' $$cid 2>/dev/null || echo starting); \
		if [ "$$status" = healthy ]; then break; fi; \
		if [ "$$status" = unhealthy ]; then echo "API is unhealthy. See: make logs"; exit 1; fi; \
		i=$$((i+1)); sleep 2; \
	done; \
	if [ "$$status" != healthy ]; then echo "Timed out waiting for the API (last status: $$status). See: make logs"; exit 1; fi; \
	echo "API healthy: http://localhost:$(API_PORT)"

down: ## Stop the stack (keeps the Postgres data volume)
	docker compose down

reset: ## Stop the stack AND DELETE the Postgres data volume (all data and conversations are lost)
	docker compose down -v

logs: ## Follow the API container logs
	docker compose logs -f api

test: ## Run the backend test suite (needs the db up: make db)
	cd backend && uv run pytest -q

eval: ## Run the agent evaluation set
	cd backend && uv run python -m eval.run

chat: ## Interactive CLI chat (pass traces with: make chat ARGS=--debug)
	cd backend && uv run python cli.py $(ARGS)

ingest: ## Run the PDF ingestion script (e.g. make ingest ARGS=--force)
	cd backend && uv run python ingest.py $(ARGS)

db: ## Start only the Postgres container
	docker compose up -d db

recovery: ## Self-healing e2e on the real stack (ARGS=--yes also runs the destructive down -v step)
	bash backend/tests/e2e/recovery.sh $(ARGS)
