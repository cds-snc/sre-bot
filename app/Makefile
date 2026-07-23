.PHONY: dev dev-setup fmt install lint test test-unit test-integration test-legacy test-all fmt-ci lint-ci install-dev run test-coverage test-coverage-unit backlog-board check-prefix-guardrail audit-client-usage-matrix

RUFF_SCOPE := api tests/api

dev:
	PREFIX="dev-" SLACK__COMMAND_PREFIX="dev-" uv run uvicorn main:server_app --reload

dev-setup: # Requires to be signed in to AWS
	uv sync --extra dev
	sh ../.devcontainer/maxmind-create.sh
	sh ../.devcontainer/dynamodb-create.sh

debug:
	PREFIX="dev-" SLACK__COMMAND_PREFIX="dev-" LOG_LEVEL=DEBUG uv run uvicorn main:server_app --reload

fmt:
	uv run black . $(ARGS) --target-version py311
	uv run ruff format $(RUFF_SCOPE) $(ARGS)

install:
	uv sync

install-dev:
	uv sync --extra dev

lint:
	uv run ruff check .
	uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)

lint-types:
	@command -v uv >/dev/null 2>&1 && uv run mypy . --check-untyped-defs --explicit-package-bases || echo "⚠️  uv not installed. Run 'make install-dev' to enable type checking."

# NEW STRUCTURE: Pure unit tests
test-unit:
	uv run coverage run -m pytest tests/unit --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

# NEW STRUCTURE: Integration tests
test-integration:
	uv run coverage run -m pytest tests/integration --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

# NEW STRUCTURE: Both unit and integration (recommended going forward)
test-new:
	uv run coverage run -m pytest tests/unit tests/integration --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

# LEGACY: All legacy tests (gradual phase-out)
test-legacy:
	uv run coverage run -m pytest \
		tests/api \
		tests/modules \
		tests/integrations \
		tests/utils \
		tests/test_factory_validation.py \
		--show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

# RUN ALL: New + legacy (default, maintain backward compatibility)
test: test-new test-legacy

# ALL tests including smoke, load, performance (explicit opt-in for slower tests)
test-all:
	uv run coverage run -m pytest tests --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

# Coverage reports with focus on new structure
test-coverage-unit:
	uv run coverage run -m pytest tests/unit --cov=modules --cov=core --cov=api --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m && \
	uv run coverage html

test-coverage-integration:
	uv run coverage run -m pytest tests/integration --cov=modules --cov=integrations --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m && \
	uv run coverage html

test-coverage-all:
	uv run coverage run -m pytest tests/unit tests/integration --cov --cov-report=html --show-capture=log --log-level=INFO -r fE && \
	uv run coverage report -m

lint-ci:
	uv run ruff check .
	uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)
	@command -v uv >/dev/null 2>&1 && uv run mypy . --check-untyped-defs || true

fmt-ci:
	uv run black --check . --target-version py311
	uv run ruff format --check $(RUFF_SCOPE)

check-prefix-guardrail:
	python bin/check_prefix_command_namespace.py

audit-client-usage-matrix:
	bash bin/generate_client_usage_matrix.sh

backlog-board: # Backlog.md web UI (Kanban board) at http://localhost:6421
	cd .. && backlog browser --no-open --port 6421

run:
	uv run uvicorn main:server_app
