.PHONY: dev dev-setup fmt install lint test fmt-ci lint-ci install-dev run

dev:
	PREFIX="dev-" python3 -m uvicorn main:server_app --reload

dev-setup: # Requires to be signed in to AWS
	pip3 install --user -r requirements_dev.txt
	pip3 install --user -r requirements.txt
	sh ../.devcontainer/maxmind-create.sh
	sh ../.devcontainer/dynamodb-create.sh

fmt:
	black . $(ARGS) --target-version py311

install:
	pip3 install --user -r requirements.txt

install-dev:
	pip3 install --user -r requirements_dev.txt

lint:
	flake8 .

test:
	python3 -m coverage run -m pytest -s -vv tests &&\
	python3 -m coverage report -m

lint-ci:
	flake8 .

fmt-ci:
	black --check . --target-version py311

run:
	uvicorn main:server_app