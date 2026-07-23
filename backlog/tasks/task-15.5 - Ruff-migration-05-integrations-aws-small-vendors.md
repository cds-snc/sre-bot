---
id: TASK-15.5
title: 'Ruff migration 05: integrations aws + small vendors'
status: To Do
assignee: []
created_date: '2026-07-23 14:17'
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
