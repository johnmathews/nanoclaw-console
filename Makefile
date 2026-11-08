# The NanoClaw console's local CI. `make ci` is what runs before every push (docs/development.md);
# GitHub runs only the lean job in .github/workflows/ci.yml, which gates the image publish.

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

PY_PROJECTS := api broker
NPM := npx -y npm@11
APP_IMAGE ?= nanoclaw-console:local
BROKER_IMAGE ?= nanoclaw-console-broker:local
PLATFORM := linux/amd64

.PHONY: help install lint typecheck test e2e design-check ci build build-app build-broker compose-smoke

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install the locked dependencies of api/, broker/ and web/
	@for p in $(PY_PROJECTS); do (cd $$p && uv sync --locked) || exit 1; done
	cd web && $(NPM) ci

lint: ## ruff (check and format) on api/ and broker/; oxlint, eslint and prettier on web/
	@for p in $(PY_PROJECTS); do (cd $$p && uv run ruff check . && uv run ruff format --check .) || exit 1; done
	cd web && npm run lint && npm run format:check

typecheck: ## mypy --strict on api/ and broker/; vue-tsc on web/
	@for p in $(PY_PROJECTS); do (cd $$p && uv run mypy) || exit 1; done
	cd web && npm run type-check

test: ## Unit tests with coverage floors: pytest on api/ and broker/, vitest on web/
	@for p in $(PY_PROJECTS); do (cd $$p && uv run coverage run -m pytest && uv run coverage report) || exit 1; done
	cd web && npm run test:coverage

e2e: ## Playwright and axe against the production build (vite preview), /api mocked
	cd web && npx playwright install chromium && npm run test:e2e

design-check: ## The design-system gate, and tokens.css generated from tokens.json
	python3 scripts/check_design_system.py brand/design-system --complete
	scripts/check-tokens.sh

ci: ## Everything above, in order, stopping at the first failure
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) e2e
	$(MAKE) design-check

build: build-app build-broker ## Build both images for amd64

build-app:
	docker build --platform $(PLATFORM) -t $(APP_IMAGE) .

build-broker:
	docker build --platform $(PLATFORM) -t $(BROKER_IMAGE) broker

compose-smoke: build-app ## Start the app image hardened as deployed; check /healthz, the 403s and the audit volume
	APP_IMAGE=$(APP_IMAGE) scripts/compose-smoke.sh
