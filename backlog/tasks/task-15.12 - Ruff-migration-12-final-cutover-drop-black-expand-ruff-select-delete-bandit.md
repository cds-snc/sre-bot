---
id: TASK-15.12
title: >-
  Ruff migration 12: final cutover -- drop black, expand ruff select, delete
  bandit
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:19'
updated_date: '2026-07-23 21:28'
labels: []
dependencies:
  - TASK-15.11
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 69000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE branch-from-main step, but this PR is CONFIG ONLY -- no source reflow (every file was already migrated by TASK-15.1..11). It removes the transitional scaffolding and lands the end-state toolchain, making the tree byte-identical to feat/dev_env_setup_ruff.

Steps:
  git checkout main && git pull
  git checkout -b <branch>
  # Adopt the end-state config verbatim from the reference branch (this drops the
  # transitional [tool.black]/force-exclude and RUFF_SCOPE, expands ruff select,
  # removes black from dev deps, and restores ruff-only fmt/lint targets):
  git checkout feat/dev_env_setup_ruff -- app/pyproject.toml app/Makefile app/uv.lock .github/workflows/log_workflow_error.yml
  # Delete the standalone bandit scan (S rules now cover the whole tree):
  git rm .github/workflows/bandit_security_scan.yml .github/workflows/scripts/run_bandit_scan.sh
  # Refresh the lock to guarantee consistency after black removal:
  cd app && uv sync --extra dev

What the checkout lands (for reviewers):
  - pyproject: select = [E,F,W,I,B,UP,C4,SIM,S]; per-file-ignores for tests + utils/tests.py; NO [tool.black]; black removed from [project.optional-dependencies].dev.
  - Makefile: fmt = ruff format .; fmt-ci = ruff format --check .; lint/lint-ci = ruff check . (+ mypy soft-fail unchanged); RUFF_SCOPE removed.
  - log_workflow_error.yml: the '- Source code security scan using Bandit' trigger line removed.

Validate (whole tree, ruff only now):
  cd app && make lint-ci && make fmt-ci && make test
Final sanity (must be EMPTY):
  git diff feat/dev_env_setup_ruff -- app .github

Note: the 'mypy ... || true' soft-fail in lint-ci is intentionally left as-is (tracked separately as toolchain migration debt, out of scope for TASK-15). Call this out in the PR description so it is not flagged as missed scope.
Expected size: ~6 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/pyproject.toml, app/Makefile, app/uv.lock, .github/workflows/log_workflow_error.yml match feat/dev_env_setup_ruff; black absent from all dependency groups and Makefile targets; ruff select is [E,F,W,I,B,UP,C4,SIM,S]
- [ ] #2 .github/workflows/bandit_security_scan.yml and .github/workflows/scripts/run_bandit_scan.sh are deleted
- [ ] #3 git diff feat/dev_env_setup_ruff -- app .github is empty (the whole migration now equals the reference branch); make lint-ci && make fmt-ci && make test pass over the whole tree with ruff only
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->
