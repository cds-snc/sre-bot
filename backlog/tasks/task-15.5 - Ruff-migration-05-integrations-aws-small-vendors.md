---
id: TASK-15.5
title: 'Ruff migration 05: integrations aws + small vendors'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:17'
updated_date: '2026-07-23 17:46'
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
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/integrations/aws app/integrations/utils app/integrations/maxmind app/integrations/trello app/integrations/notify app/integrations/sentinel app/integrations/opsgenie app/tests/integrations/aws app/tests/integrations/utils app/tests/integrations/maxmind app/tests/integrations/trello app/tests/integrations/notify app/tests/integrations/sentinel app/tests/integrations/opsgenie app/tests/unit/integrations is empty
- [ ] #2 force-exclude + RUFF_SCOPE include all listed integrations src/test dirs plus tests/unit/integrations; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
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
