.PHONY: dev fmt install lint test fmt-ci lint-ci install-dev run

dev:
	jurigged main.py

fmt:
	black . $(ARGS) --target-version py310

install:
	pip3 install --user -r requirements.txt

install-dev:
	pip3 install --user -r requirements_dev.txt

lint:
	flake8 .

test:
	coverage run -m pytest -s -vv tests &&\
	coverage report -m

lint-ci:
	flake8 .

fmt-ci:
	black --check .

run:
	python3 main.py