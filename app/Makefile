.PHONY: dev dev-setup fmt install lint test test-unit test-integration test-legacy test-all fmt-ci lint-ci install-dev run test-coverage test-coverage-unit

dev:
	PREFIX="dev-" python3 -m uvicorn main:server_app --reload

dev-setup: # Requires to be signed in to AWS
	pip3 install --user -r requirements_dev.txt
	pip3 install --user -r requirements.txt
	sh ../.devcontainer/maxmind-create.sh
	sh ../.devcontainer/dynamodb-create.sh

debug:
	PREFIX="dev-" LOG_LEVEL=DEBUG python3 -m uvicorn main:server_app --reload

fmt:
	black . $(ARGS) --target-version py311

install:
	pip3 install --user -r requirements.txt

install-dev:
	pip3 install --user -r requirements_dev.txt

lint:
	flake8 .

lint-types:
	@command -v mypy >/dev/null 2>&1 && mypy . --check-untyped-defs --explicit-package-bases || echo "⚠️  mypy not installed. Run 'make install-dev' to enable type checking."

# NEW STRUCTURE: Pure unit tests
test-unit:
	python3 -m coverage run -m pytest tests/unit --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

# NEW STRUCTURE: Integration tests
test-integration:
	python3 -m coverage run -m pytest tests/integration --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

# NEW STRUCTURE: Both unit and integration (recommended going forward)
test-new:
	python3 -m coverage run -m pytest tests/unit tests/integration --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

# LEGACY: All legacy tests (gradual phase-out)
test-legacy:
	python3 -m coverage run -m pytest \
		tests/api \
		tests/core \
		tests/modules \
		tests/server \
		tests/jobs \
		tests/integrations \
		tests/models \
		tests/utils \
		tests/test_factory_validation.py \
		--show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

# RUN ALL: New + legacy (default, maintain backward compatibility)
test: test-new test-legacy

# ALL tests including smoke, load, performance (explicit opt-in for slower tests)
test-all:
	python3 -m coverage run -m pytest tests --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

# Coverage reports with focus on new structure
test-coverage-unit:
	python3 -m coverage run -m pytest tests/unit --cov=modules --cov=core --cov=api --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m && \
	python3 -m coverage html

test-coverage-integration:
	python3 -m coverage run -m pytest tests/integration --cov=modules --cov=integrations --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m && \
	python3 -m coverage html

test-coverage-all:
	python3 -m coverage run -m pytest tests/unit tests/integration --cov --cov-report=html --show-capture=log --log-level=INFO -r fE && \
	python3 -m coverage report -m

lint-ci:
	flake8 .
	@command -v mypy >/dev/null 2>&1 && mypy . --check-untyped-defs || true

fmt-ci:
	black --check . --target-version py311

run:
	uvicorn main:server_app