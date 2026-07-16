---
id: TASK-17
title: Add pre-commit running the same hooks locally and in CI
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-15
  - TASK-16
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1271'
priority: medium
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (CI gates). No .pre-commit-config.yaml exists today.

Steps:
1. Create .pre-commit-config.yaml with: ruff format, ruff check, mypy (via local hook running the project venv so versions match), uv lock --check, plus standard hygiene hooks (end-of-file, trailing whitespace, YAML syntax).
2. CI job runs pre-commit run --all-files (or prek, its config-compatible successor - pick one and note it in the config header).
3. Document the one-time local setup (pre-commit install) in the README developer section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 .pre-commit-config.yaml exists; pre-commit run --all-files passes locally
- [ ] #2 CI has a job running the same hooks over all files
- [ ] #3 Hook tool versions match the project versions (mypy/ruff run from the project environment)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 README documents setup
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->
