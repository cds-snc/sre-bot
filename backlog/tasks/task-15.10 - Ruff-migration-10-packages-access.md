---
id: TASK-15.10
title: 'Ruff migration 10: packages/access'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:19'
updated_date: '2026-07-23 20:59'
labels: []
dependencies:
  - TASK-15.9
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the packages/access feature package and its unit tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access

Note: packages/access/sync/application.py carries reviewed S101 type-narrowing noqa markers (asserts guarded by preceding error checks) from the branch -- keep verbatim.

app/pyproject.toml -> add to [tool.black] force-exclude:
    | packages/access
    | tests/unit/packages/access

app/Makefile -> append to RUFF_SCOPE:
    packages/access tests/unit/packages/access

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~60 files. If reviewers require <50, split into two PRs by access sub-package: (a) packages/access/sync + packages/access/common, (b) packages/access/catalog + packages/access/request -- pulling the matching tests/unit/packages/access/* files with each. Keep the force-exclude/RUFF_SCOPE entries at the granular sub-package level in that case.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access is empty
- [ ] #2 force-exclude + RUFF_SCOPE include packages/access and tests/unit/packages/access; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch (done): feat/dev_env_setup_ruff_10, branched from main after TASK-15.9 merged.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access -> 60 files changed, no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~60 files in the task description.
   Note: packages/access/sync/application.py carries reviewed S101 type-narrowing noqa markers (4 occurrences: "assert adapter is not None  # noqa: S101 ..." / "assert effective is not None  # noqa: S101 ...", guarded by preceding error checks) -- confirmed present in the reference branch diff; keep verbatim, do not edit.
3. Edit app/pyproject.toml [tool.black] force-exclude: append to the existing alternation (after tests/unit/models, before the closing )/'''):
     | packages/access
     | tests/unit/packages/access
   Leave [tool.ruff.lint] select/extend-select and all prior force-exclude entries (api, infrastructure, integrations, modules, utils, models, jobs, bin, server + their test dirs) unchanged.
4. Edit app/Makefile RUFF_SCOPE (line 3): append 'packages/access tests/unit/packages/access' to the existing space-separated list. Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already generic, using $(RUFF_SCOPE)).
5. Edit .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS (line 23) to stay in sync: append ,/data/app/packages/access,/data/app/tests/unit/packages/access to the comma-separated list.
6. Validate from app/: make lint-ci && make fmt-ci (both ruff invocations + black --check must pass). Run a scoped pytest first to keep iteration fast: uv run pytest tests/unit/packages/access -q. Defer the full `make test` (long-running) to the user to run directly as the final DoD check before closing this task -- do not run it as the agent.
7. Confirm git diff feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access is empty (AC#1).
8. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15. No split into sub-PRs needed since 60 files is within the task's own stated tolerance and matches the established single-PR pattern of prior TASK-15.x siblings (pure mechanical formatting/typing churn, no behavior change).

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 2, verified by step 7.
- AC#2 (force-exclude + RUFF_SCOPE include packages/access and tests/unit/packages/access; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 6.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 6 (user-run, deferred) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->
