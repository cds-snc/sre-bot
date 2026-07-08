---
id: TASK-44
title: >-
  Consolidate dev tooling at the repo root: uv project layout and single
  Makefile entry point
status: To Do
assignee: []
created_date: '2026-07-08 15:04'
updated_date: '2026-07-08 16:27'
labels:
  - toolchain
milestone: m-1
dependencies: []
references:
  - Makefile
  - app/Makefile
  - app/pyproject.toml
priority: medium
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A root Makefile now forwards unknown targets to app/Makefile (added 2026-07-08) so dev commands work from the repo root, which is the conventional pattern. That is a stopgap: the underlying layout still has pyproject.toml, uv.lock, and all tooling config living in app/ while backlog/, decisions/, terraform/, and tests/ live at the root.

Decide and implement the durable structure:
1. Evaluate moving pyproject.toml + uv.lock to the repo root (uv supports running against a nested project via --project/--directory, and root-level metadata is what most tools — ruff, mypy, pytest, pre-commit, Renovate, IDEs — resolve by default). Alternative: a uv workspace with app/ as a member if more packages are expected.
2. Align every consumer of the current layout: Dockerfile build context, CI workflows, devcontainer, and any script assuming cwd=app/.
3. Keep root Makefile as the single entry point; app/Makefile either disappears or becomes internal.
4. Record the outcome in decisions/ (toolchain or structure decision record).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All routine dev commands (test, lint, fmt, dev, install) run from the repo root without cd app/
- [ ] #2 uv resolves the project from the repo root (root pyproject/workspace or documented --project pattern); CI, Dockerfile, and devcontainer updated accordingly
- [ ] #3 Decision record in decisions/ documents the chosen layout and why
<!-- AC:END -->
