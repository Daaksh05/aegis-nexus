.PHONY: up down logs test lint format doctor contracts

contracts:
	python3 services/api/scripts/export_openapi.py
	cd apps/web && npm run generate:api

up:
	docker compose -f infra/docker-compose.yml --env-file .env up -d

down:
	docker compose -f infra/docker-compose.yml --env-file .env down

logs:
	docker compose -f infra/docker-compose.yml --env-file .env logs -f

test:
	@if [ -z "$$(find services/api -type f ! -name .gitkeep -print -quit)" ]; then \
		echo "Skipping API tests: services/api contains only .gitkeep."; \
	else \
		python3 -m pytest; \
	fi
	@if [ -z "$$(find apps/web -type f ! -name .gitkeep -print -quit)" ]; then \
		echo "Skipping web tests: apps/web contains only .gitkeep."; \
	else \
		cd apps/web && npm test; \
	fi

lint:
	@if [ -z "$$(find services/api -type f ! -name .gitkeep -print -quit)" ]; then \
		echo "Skipping API lint: services/api contains only .gitkeep."; \
	else \
		ruff check services/api services/engine; \
	fi
	@if [ -z "$$(find apps/web -type f ! -name .gitkeep -print -quit)" ]; then \
		echo "Skipping web lint: apps/web contains only .gitkeep."; \
	else \
		cd apps/web && npm run lint; \
	fi

format:
	ruff format services/api services/engine
	@if [ -n "$$(find apps/web -type f ! -name .gitkeep -print -quit)" ]; then \
		cd apps/web && npx prettier --write .; \
	else \
		echo "Skipping web format: apps/web contains only .gitkeep."; \
	fi

doctor:
	@command -v docker >/dev/null 2>&1 || { echo "doctor: Docker CLI is missing. Install Docker Desktop and ensure docker is on PATH." >&2; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "doctor: Python 3 is missing. Install Python $$(tr -d '[:space:]' < .python-version)." >&2; exit 1; }
	@expected="$$(tr -d '[:space:]' < .python-version)"; \
	actual="$$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"; \
	if [ "$$actual" != "$$expected" ]; then \
		echo "doctor: Python version mismatch (expected $$expected, found $$actual)." >&2; exit 1; \
	fi
	@command -v node >/dev/null 2>&1 || { echo "doctor: Node.js is missing. Install Node.js $$(tr -d '[:space:]v' < .nvmrc)." >&2; exit 1; }
	@expected="$$(tr -d '[:space:]v' < .nvmrc)"; \
	actual="$$(node -p 'process.versions.node.split(".")[0]')"; \
	if [ "$$actual" != "$$expected" ]; then \
		echo "doctor: Node.js version mismatch (expected major $$expected, found $$actual)." >&2; exit 1; \
	fi
	@echo "doctor: Docker, Python, and Node.js match the project version pins."
