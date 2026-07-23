---
id: TASK-15.1
title: 'Ruff migration 01: scaffold parallel black/ruff CI + migrate app/api'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:11'
updated_date: '2026-07-23 15:41'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch: git checkout main && git pull && git checkout -b <branch-name> (human/PR step, not run by agent).
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/api app/tests/api
   Verified against current main: 8 of 12 tracked files under these paths actually change content (app/api/router.py, app/api/v1/router.py, app/api/v1/routes/geolocate.py, app/api/v1/routes/webhooks.py, app/tests/api/dependencies/test_rate_limits.py, app/tests/api/routes/test_landing.py, app/tests/api/v1/test_geolocate.py, app/tests/api/v1/test_webhooks.py); 4 are byte-identical already (app/api/__init__.py, app/api/routes/landing.py, app/api/routes/system.py, app/tests/api/routes/test_system.py) -- confirmed via git diff main feat/dev_env_setup_ruff -- <path> (empty for all 4). Non-py tracked assets (app/api/routes/favicon.ico, app/api/routes/landing_content.json) are untouched by ruff/black, no action needed.
3. Edit app/pyproject.toml (insert after line 71 "mccabe.max-complexity = 16", before line 73 "[tool.mypy]"):
   [tool.ruff.lint.per-file-ignores]
   "tests/**" = ["S101", "S105", "S106", "S107", "B007", "B008", "B011", "B017", "B018", "B905", "C408", "C416", "C418", "SIM116", "SIM117", "SIM118", "UP028"]
   "utils/tests.py" = ["S101"]

   [tool.black]
   target-version = ["py311"]
   force-exclude = '''
   /(
       api
     | tests/api
   )/
   '''
   Leave [tool.ruff.lint] select = ["E","F","W"] (line 69) and ignore/mccabe (lines 70-71) unchanged. Leave black in [project.optional-dependencies].dev (line 43) unchanged.
4. Edit app/Makefile:
   a. After line 1 (.PHONY ...), add: RUFF_SCOPE := api tests/api
   b. fmt target (line 14-15): append a second recipe line "uv run ruff format $(RUFF_SCOPE) $(ARGS)" after the existing black line.
   c. lint target (line 23-24): append a second recipe line "uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)" after the existing "uv run ruff check ." line.
   d. lint-ci target (line 78-80): insert "uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S $(RUFF_SCOPE)" between the existing "uv run ruff check ." line and the mypy "|| true" line.
   e. fmt-ci target (line 82-83): append a second recipe line "uv run ruff format --check $(RUFF_SCOPE)" after the existing black --check line.
   Do not touch test/test-unit/test-integration/lint-types targets.
5. cd app && uv sync --extra dev (refresh lock only if pyproject changed structurally; dependency list itself is unchanged here so this is a no-op safety check).
6. Validate from app/: make lint-ci && make fmt-ci && make test. All three simulated in an isolated worktree during planning (git worktree, content pulled from feat/dev_env_setup_ruff, config edits applied, discarded after): uv run ruff check . -> All checks passed; uv run ruff check --select=E,F,W,I,B,UP,C4,SIM,S api tests/api -> All checks passed; uv run black --check . --target-version py311 -> 649 files unchanged (api/tests/api correctly force-excluded); uv run ruff format --check api tests/api -> 12 files already formatted; make test -> 1812 passed/37 skipped + 1049 passed (test-unit + legacy), 0 failures. mypy remains soft-failing via existing "|| true" with 126 pre-existing errors in unrelated legacy modules (modules/incident, integrations/aws, etc.) -- unchanged by this PR, not a regression, out of scope (tracked separately per decisions/toolchain.md migration debt).
7. Do not touch .github/workflows/bandit_security_scan.yml or any CI workflow file -- .github/workflows/ci_code.yml already calls "make lint-ci" / "make fmt-ci" / "make test" generically, so no workflow edits are needed for this slice.
8. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (parallel CI green) <- steps 3, 4, 6 (validated by dry-run above).
- AC#2 (app/api, app/tests/api byte-identical to feat/dev_env_setup_ruff) <- step 2; verify with "git diff feat/dev_env_setup_ruff -- app/api app/tests/api" (must be empty after checkout).
- AC#3 (pyproject force-exclude + per-file-ignores added, global select stays E,F,W, black stays in dev deps, Makefile has RUFF_SCOPE + dual targets) <- steps 3, 4; verify by reading the edited sections.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 6 (test run) + PR description (human/PR action).

Test matrix:
- Happy path: make lint-ci (both ruff invocations pass, mypy soft-fails as today) and make fmt-ci (black --check whole tree minus api/tests/api, ruff format --check on RUFF_SCOPE) both exit 0.
- Regression: make test unchanged pass count vs current main baseline (1812+1049 passed in the dry run); any new failure is a real regression in the migrated api/tests/api content, not expected from a mechanical pull.
- Config-only check: grep -n "RUFF_SCOPE" app/Makefile and grep -n "force-exclude" app/pyproject.toml both hit exactly once.

Assumptions / doubts (verified during planning, not guessed):
- Reference branch feat/dev_env_setup_ruff has already fully cut over (no black anywhere, global ruff select already E,F,W,I,B,UP,C4,SIM,S, per-file-ignores already present) -- confirmed via git show feat/dev_env_setup_ruff:app/pyproject.toml. This PR's [tool.black] section is authored fresh for the transitional state and does not come from the reference branch.
- No import-linter / lint-imports config exists yet in app/ (grep found none) -- reordered imports in api/router.py and api/v1/router.py from the reference branch cannot trip a contract that does not exist; not a concern for this slice.
- __pycache__ artifacts under app/api and app/tests/api are gitignored (confirmed via git check-ignore) and not tracked; only favicon.ico and landing_content.json are tracked non-.py files and are unaffected by black/ruff.

Blast radius and rollback:
- Blast radius: app/pyproject.toml, app/Makefile, and 8 content files under app/api + app/tests/api. No route behavior, schema, or business logic changes -- purely import ordering/formatting/typing-syntax churn plus one added noqa comment (api/v1/routes/webhooks.py, B008, already justified inline). No changes to CI workflow files, other app/ paths, or dependencies.
- Rollback: revert the single PR commit; both toolchains remain independently invertible (removing RUFF_SCOPE/[tool.black] restores prior single-toolchain Makefile/pyproject; re-checking out api/tests/api from main restores pre-migration source).
<!-- SECTION:PLAN:END -->
