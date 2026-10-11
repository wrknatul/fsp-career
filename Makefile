# FSP.Career: everyday commands. Run `make` to see the list.
#
# Docker targets need Docker with the Compose plugin. Backend and frontend
# targets need backend/.venv (make venv) and frontend/node_modules (npm install).

.DEFAULT_GOAL := help
.PHONY: help up down logs test lint seed-reset typecheck build-web venv

help: ## show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

up: ## build and start database, API and web in the background
	docker compose up --build -d

down: ## stop the stack (the database volume is kept)
	docker compose down

logs: ## follow logs of all services
	docker compose logs -f --tail=100

test: ## backend tests (pytest in backend/.venv)
	cd backend && .venv/bin/pytest

lint: ## backend linter (ruff in backend/.venv)
	cd backend && .venv/bin/ruff check app tests

seed-reset: ## recreate demo data in the running stack
	docker compose exec backend python -m app.seed --reset

typecheck: ## frontend type check
	cd frontend && npm run typecheck

build-web: ## frontend production build (type check + vite build)
	cd frontend && npm run build

venv: ## create backend/.venv with runtime and test dependencies
	python3.12 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements-dev.txt
