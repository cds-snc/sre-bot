---
id: TASK-15.1
title: 'Ruff migration 01: scaffold parallel black/ruff CI + migrate app/api'
status: To Do
assignee: []
created_date: '2026-07-23 14:11'
updated_date: '2026-07-23 14:16'
labels: []
dependencies:
  - TASK-15
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Part of the TASK-15 incremental rollout. Splits the 484-file big-bang ruff migration (reference branch feat/dev_env_setup_ruff) into ~50-file PRs. Each PR moves a slice of the tree from the LEGACY toolchain (black @ width 88 + ruff lint E,F,W) onto RUFF (ruff format @ width 130 + ruff lint E,F,W,I,B,UP,C4,SIM,S). Both toolchains run in the SAME CI over their OWN scope, so main stays green throughout.

This first PR establishes the parallel-CI scaffolding and migrates the smallest slice (app/api + app/tests/api) as a pilot.

=== SHARED RECIPE (every TASK-15.x PR) ===
1. Branch from latest main AFTER the previous TASK-15.x PR merged:
     git checkout main && git pull
     git checkout -b <branch>
2. Pull already-migrated content for THIS PR's paths from the reference branch (never hand-edit migrated source):
     git checkout feat/dev_env_setup_ruff -- <PATHS>
   Unchanged files are byte-identical to main; changed files arrive in their final ruff form.
3. Move THIS PR's paths into the migrated set in TWO places:
     a. app/pyproject.toml -> [tool.black] force-exclude regex  (black stops checking them)
     b. app/Makefile -> RUFF_SCOPE variable                     (ruff starts checking them)
4. Validate from app/:  make lint-ci && make fmt-ci && make test
5. Ship ONE mechanical PR; reference decisions/toolchain.md + TASK-15. Migrated content must equal the reference branch.

=== THIS PR: scaffold + pilot ===
Paths to pull:
  git checkout feat/dev_env_setup_ruff -- app/api app/tests/api

Edit app/pyproject.toml:
  - KEEP [tool.ruff.lint] select = ["E","F","W"] UNCHANGED (do not expand globally yet).
  - KEEP black in [project.optional-dependencies].dev unchanged.
  - ADD the tests/idiom per-file-ignores (end-state values; inert for global E,F,W, active only when a test path is scoped-linted):
      [tool.ruff.lint.per-file-ignores]
      "tests/**" = ["S101","S105","S106","S107","B007","B008","B011","B017","B018","B905","C408","C416","C418","SIM116","SIM117","SIM118","UP028"]
      "utils/tests.py" = ["S101"]
  - ADD the transitional black force-exclude section (grown by every later PR):
      [tool.black]
      target-version = ["py311"]
      force-exclude = '''
      /(
          api
        | tests/api
      )/
      '''

Edit app/Makefile -- replace the fmt/lint/fmt-ci/lint-ci targets with the transitional versions below. Each recipe line under a target MUST start with a real TAB (shown here as the >>> marker; keep the dollar-parens Make refs exactly):
      RUFF_SCOPE := api tests/api

      fmt:
      >>>uv run black . $(ARGS) --target-version py311
      >>>uv run ruff format $(RUFF_SCOPE) $(ARGS)

      lint:
      >>>uv run ruff check .
      >>>uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)

      fmt-ci:
      >>>uv run black --check . --target-version py311
      >>>uv run ruff format --check $(RUFF_SCOPE)

      lint-ci:
      >>>uv run ruff check .
      >>>uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)
      >>>@command -v uv >/dev/null 2>&1 && uv run mypy . --check-untyped-defs || true

Notes:
- black --check . reads [tool.black] force-exclude from pyproject, so migrated paths are skipped automatically -- no per-command regex needed.
- Do NOT delete the bandit workflow here; S (security) rules only cover migrated paths until the final cutover PR (TASK-15.12).
- Expected size: ~8 files + config. Validate: cd app && make lint-ci && make fmt-ci && make test
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Parallel CI is green: black --check . (legacy scope, migrated paths force-excluded) passes AND ruff format --check plus ruff check --select=E,F,W,I,B,UP,C4,SIM,S over RUFF_SCOPE (api tests/api) pass
- [ ] #2 app/api and app/tests/api are byte-identical to feat/dev_env_setup_ruff: git diff feat/dev_env_setup_ruff -- app/api app/tests/api is empty
- [ ] #3 pyproject gains [tool.black] force-exclude + tests per-file-ignores; global ruff select stays [E,F,W]; black still present in dev deps; Makefile has RUFF_SCOPE and dual black+ruff fmt-ci/lint-ci
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->
