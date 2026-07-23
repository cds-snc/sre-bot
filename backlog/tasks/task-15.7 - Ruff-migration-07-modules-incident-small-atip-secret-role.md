---
id: TASK-15.7
title: 'Ruff migration 07: modules incident + small (atip, secret, role)'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:18'
updated_date: '2026-07-23 19:07'
labels: []
dependencies:
  - TASK-15.6
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates modules/incident plus the small modules (atip, secret, role) and their tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/modules/incident app/modules/atip app/modules/secret app/modules/role \
    app/tests/modules/incident app/tests/modules/secret app/tests/modules/role app/tests/unit/modules/atip

Note: modules/secret/secret.py is the actual secrets module and carries carefully-reviewed S-family noqa markers from the checkout -- keep them verbatim; do NOT reflexively add/remove noqa. modules/incident files carry reviewed B904/SIM/S fixes from the branch. modules/atip had an unmerged PR that we are going to merge prior to starting this task. This means the feat/dev_env_setup_ruff branch may have diverging content from main on modules/atip and its tests. We will need to keep the logic change from main but migrate or adjust its formatting from to align with the reference branch feat/dev_env_setup_ruff 

app/pyproject.toml -> add to [tool.black] force-exclude:
    | modules/incident
    | modules/atip
    | modules/secret
    | modules/role
    | tests/modules/incident
    | tests/modules/secret
    | tests/modules/role
    | tests/unit/modules/atip

app/Makefile -> append to RUFF_SCOPE:
    modules/incident modules/atip modules/secret modules/role tests/modules/incident tests/modules/secret tests/modules/role tests/unit/modules/atip

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~38 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/modules/incident app/modules/atip app/modules/secret app/modules/role app/tests/modules/incident app/tests/modules/secret app/tests/modules/role app/tests/unit/modules/atip is empty
- [x] #2 force-exclude + RUFF_SCOPE include all listed module src/test dirs; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TASK-15.7 per TASK-15.1 shared recipe with ATIP divergence handling.\n- Pulled migrated content from feat/dev_env_setup_ruff for non-ATIP paths: app/modules/{incident,secret,role} and app/tests/modules/{incident,secret,role}.\n- Preserved current main-branch logic for app/modules/atip and app/tests/unit/modules/atip to keep COMMAND_PREFIX behavior; applied Ruff-compatible formatting/lint fixes only.\n- Updated app/pyproject.toml [tool.black] force-exclude with: modules/incident, modules/atip, modules/secret, modules/role, tests/modules/incident, tests/modules/secret, tests/modules/role, tests/unit/modules/atip.\n- Updated app/Makefile RUFF_SCOPE with matching module/test paths.\n- Updated .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS to keep in sync with RUFF_SCOPE.\nValidation:\n- cd app && make lint-ci -> pass (exit 0; mypy remains pre-existing soft-failing under existing || true).\n- cd app && make fmt-ci -> pass (exit 0).\n- cd app && uv run pytest tests/modules/incident tests/modules/secret tests/modules/role tests/unit/modules/atip -q -> 334 passed, 16 warnings, 0 failed.\nDiff verification:\n- git diff feat/dev_env_setup_ruff -- app/modules/incident app/modules/secret app/modules/role app/tests/modules/incident app/tests/modules/secret app/tests/modules/role -> empty.\n- Remaining intentional divergence vs feat/dev_env_setup_ruff (for COMMAND_PREFIX/main logic): app/modules/atip/atip.py, app/tests/unit/modules/atip/test_atip.py, app/tests/unit/modules/atip/test_atip_command_registration.py.\nDoD pending: per instruction, full make test deferred to user as very last step to save tokens.

\nFinal verification: user ran `make test` from /workspace and confirmed all tests green (exit 0).
<!-- SECTION:NOTES:END -->
