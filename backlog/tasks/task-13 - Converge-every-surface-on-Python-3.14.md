---
id: TASK-13
title: Converge every surface on Python 3.14
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies: []
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1267'
priority: high
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Python). Today: CI pins 3.11, the venv is 3.12, the Docker image runs python:3.14-slim, and ruff/mypy target 3.11 - production runs an interpreter two minors ahead of everything that tests the code.

Steps:
1. Set .python-version to 3.14 (create if absent, at app/ working root).
2. Update every GitHub Actions workflow python-version to 3.14.
3. Confirm the Dockerfile base stays python:3.14-slim.
4. Set requires-python = ">=3.13" (no upper bound) in app/pyproject.toml; set ruff target-version and mypy python_version to 3.14 equivalents.
5. Recreate the local venv on 3.14 (uv python pin + uv sync); run the full test suite on 3.14 and fix any incompatibilities found.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep across .python-version, workflows, and Dockerfile shows exactly one Python version: 3.14
- [ ] #2 CI runs green on 3.14
- [ ] #3 ruff and mypy target versions match
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Full test suite passes on 3.14 locally and in CI
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->
