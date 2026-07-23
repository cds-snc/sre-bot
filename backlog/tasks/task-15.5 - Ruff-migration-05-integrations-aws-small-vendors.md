---
id: TASK-15.5
title: 'Ruff migration 05: integrations aws + small vendors'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:17'
updated_date: '2026-07-23 18:21'
labels: []
dependencies:
  - TASK-15.4
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the aws integration plus the small vendor integrations (utils, maxmind, trello, notify, sentinel, opsgenie) and the tests/unit/integrations tree.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/integrations/aws app/integrations/utils app/integrations/maxmind app/integrations/trello app/integrations/notify app/integrations/sentinel app/integrations/opsgenie \
    app/tests/integrations/aws app/tests/integrations/utils app/tests/integrations/maxmind app/tests/integrations/trello app/tests/integrations/notify app/tests/integrations/sentinel app/tests/integrations/opsgenie \
    app/tests/unit/integrations

Note: several of these files carry individually-reviewed S105/S106/S107 noqa markers (non-secret header/field names) that arrive via the checkout -- keep them verbatim; do not add or remove noqa.

app/pyproject.toml -> add to [tool.black] force-exclude:
    | integrations/aws
    | integrations/utils
    | integrations/maxmind
    | integrations/trello
    | integrations/notify
    | integrations/sentinel
    | integrations/opsgenie
    | tests/integrations/aws
    | tests/integrations/utils
    | tests/integrations/maxmind
    | tests/integrations/trello
    | tests/integrations/notify
    | tests/integrations/sentinel
    | tests/integrations/opsgenie
    | tests/unit/integrations

app/Makefile -> append to RUFF_SCOPE:
    integrations/aws integrations/utils integrations/maxmind integrations/trello integrations/notify integrations/sentinel integrations/opsgenie tests/integrations/aws tests/integrations/utils tests/integrations/maxmind tests/integrations/trello tests/integrations/notify tests/integrations/sentinel tests/integrations/opsgenie tests/unit/integrations

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~51 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 git diff feat/dev_env_setup_ruff -- app/integrations/aws app/integrations/utils app/integrations/maxmind app/integrations/trello app/integrations/notify app/integrations/sentinel app/integrations/opsgenie app/tests/integrations/aws app/tests/integrations/utils app/tests/integrations/maxmind app/tests/integrations/trello app/tests/integrations/notify app/tests/integrations/sentinel app/tests/integrations/opsgenie app/tests/unit/integrations is empty
- [x] #2 force-exclude + RUFF_SCOPE include all listed integrations src/test dirs plus tests/unit/integrations; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch from latest main (done): feat/dev_env_setup_ruff_5, branched after TASK-15.4 merged.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/integrations/aws app/integrations/utils app/integrations/maxmind app/integrations/trello app/integrations/notify app/integrations/sentinel app/integrations/opsgenie app/tests/integrations/aws app/tests/integrations/utils app/tests/integrations/maxmind app/tests/integrations/trello app/tests/integrations/notify app/tests/integrations/sentinel app/tests/integrations/opsgenie app/tests/unit/integrations
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 51 files changed, 437 insertions(+), 951 deletions(-); no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~51 files in the task description.
   Note: several files carry individually-reviewed S105/S106/S107 noqa markers (non-secret header/field names) that arrive via the checkout -- keep them verbatim; do not add or remove noqa.
3. Edit app/pyproject.toml [tool.black] force-exclude block: add the seven integrations src alternatives and the eight test-tree alternatives inside the existing /( ... )/ group:
     | integrations/aws
     | integrations/utils
     | integrations/maxmind
     | integrations/trello
     | integrations/notify
     | integrations/sentinel
     | integrations/opsgenie
     | tests/integrations/aws
     | tests/integrations/utils
     | tests/integrations/maxmind
     | tests/integrations/trello
     | tests/integrations/notify
     | tests/integrations/sentinel
     | tests/integrations/opsgenie
     | tests/unit/integrations
   Leave [tool.ruff.lint] select = ["E","F","W"] and everything else (including the consolidated infrastructure / tests/unit/infrastructure entries from TASK-15.4) unchanged.
4. Edit app/Makefile: append to RUFF_SCOPE:
     RUFF_SCOPE := api tests/api infrastructure tests/unit/infrastructure integrations/aws integrations/utils integrations/maxmind integrations/trello integrations/notify integrations/sentinel integrations/opsgenie tests/integrations/aws tests/integrations/utils tests/integrations/maxmind tests/integrations/trello tests/integrations/notify tests/integrations/sentinel tests/integrations/opsgenie tests/unit/integrations
   Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already generic + using --extend-select per TASK-15.2's fix).
5. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/integrations/aws tests/integrations/utils tests/integrations/maxmind tests/integrations/trello tests/integrations/notify tests/integrations/sentinel tests/integrations/opsgenie tests/unit/integrations.
6. Confirm git diff feat/dev_env_setup_ruff -- <all 15 paths> is empty (AC#1).
7. Defer make test (long-running, full suite) to the user to run directly as the final check before closing this task -- do not run it as the agent.
8. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 2, verified by step 6.
- AC#2 (force-exclude + RUFF_SCOPE include all listed dirs; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 5.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 7 (user-run) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per plan (mirrors TASK-15.1/15.2/15.3/15.4 recipe):
1. git checkout feat/dev_env_setup_ruff -- app/integrations/{aws,utils,maxmind,trello,notify,sentinel,opsgenie} app/tests/integrations/{aws,utils,maxmind,trello,notify,sentinel,opsgenie} app/tests/unit/integrations (51 files, no adds/deletes -- matches expected size; verified via git diff --stat and --diff-filter=AD against main before edits). git diff feat/dev_env_setup_ruff -- <same paths> is empty (AC#1 verified). Individually-reviewed S105/S106/S107 noqa markers in the checked-out files kept verbatim; none added or removed.
2. app/pyproject.toml [tool.black] force-exclude: added the seven integrations src alternatives (aws, utils, maxmind, trello, notify, sentinel, opsgenie) and the eight test-tree alternatives (tests/integrations/{aws,utils,maxmind,trello,notify,sentinel,opsgenie}, tests/unit/integrations) inside the existing /( ... )/ group. Consolidated infrastructure / tests/unit/infrastructure entries from TASK-15.4 left unchanged.
3. app/Makefile: RUFF_SCOPE extended with all fifteen new tokens (kept existing api/tests/api/infrastructure/tests-unit-infrastructure entries). fmt/lint/fmt-ci/lint-ci target bodies untouched (already generic + using --extend-select per TASK-15.2's fix).
4. Validation: make lint-ci -> both ruff invocations "All checks passed!"; mypy soft-fails via existing "|| true" with 128 pre-existing errors, all in unrelated legacy modules/pre-existing infra debt (same count/category as TASK-15.4 notes, not a regression). make fmt-ci -> black 358 files unchanged, ruff format 295 files already formatted. uv run pytest on the migrated scope (tests/integrations/{aws,utils,maxmind,trello,notify,sentinel,opsgenie} tests/unit/integrations) -> 1 failed, 484 passed. That one failure (test_handle_final_error_logs_non_critical_and_critical, a caplog/structlog interaction issue) was verified via an isolated git worktree of the pristine feat/dev_env_setup_ruff reference branch to fail identically there -- confirmed pre-existing, not a regression introduced by this migration or the config changes.
5. DoD#1: user ran `make test` (full suite, from app/) directly and confirmed it is all green (exit 0) -- the narrower-scope failure above does not reproduce in the full make test run. DoD#1 verified.
PR should reference decisions/toolchain.md and TASK-15.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-23 18:21
---
Follow-up during this slice: the standalone Bandit CI workflow (cytopia/bandit:latest) failed to parse several already-migrated files (infrastructure/logging/setup.py, infrastructure/resilience/retry/dynamodb_store.py, infrastructure/events/models.py, infrastructure/operations/result.py, integrations/aws/client_next.py) because its bundled Python predates PEP 758 (3.14, unparenthesized except) and PEP 695 (3.12, class Foo[T]) syntax already valid under this project's actual Python 3.14 target (decisions/toolchain.md). Confirmed these are not code defects: ast.parse succeeds on Python 3.14, fails on 3.11.

Fix applied: .github/workflows/scripts/run_bandit_scan.sh now excludes every path already in app/Makefile's RUFF_SCOPE via a new RUFF_MIGRATED_PATHS list -- those paths already get ruff's S (bandit-equivalent) coverage, so this removes the false failures with zero security-coverage gap. Full early deletion of the workflow was intentionally avoided (TASK-15.1 explicitly defers that to TASK-15.12, to not leave not-yet-migrated paths unscanned).

Updated TASK-15.1's SHARED RECIPE (step 3c + Notes) so every remaining slice (TASK-15.6..15.11) keeps RUFF_MIGRATED_PATHS in sync with RUFF_SCOPE going forward.
---
<!-- COMMENTS:END -->
