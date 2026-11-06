---
id: TASK-36.1.3
title: >-
  Pin the legacy aws, talent-role, secret and atip/aiprp commands and
  interactions through the Bolt dispatch boundary
status: To Do
assignee: []
created_date: 2026-10-15 20:49
updated_date: '2026-11-06T19:12:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36.1.1
references:
  - decisions/testing.md
  - decisions/migration.md
  - https://github.com/cds-snc/sre-bot/issues/1740
parent_task_id: TASK-36.1
priority: medium
ordinal: 397000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of TASK-36.1, reusing the harness from the first slice. Pins 13 rows that TASK-88 and TASK-39 rebuild: commands /aws, /talent-role, /secret, /atip, /aiprp; views aws_health_view, role_view, secret_view, atip_view; actions role_change_locale, secret_change_locale, ati_search_width, atip_change_locale. The /aws subcommands (health, users, groups, lambdas, help) are pinned at the routing and ack level with the backing service faked.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 13 rows has a dispatch-driven test covering ack, Slack-visible calls and faked side effects, or an explicit not-pinned reason with its owning ticket
- [ ] #2 INVENTORY.md marks these rows pinned by this task
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Pin task: durable entry points, modal ids read from the opened view, outcome assertions at faked external edges, internal legacy seams only in named legacy_surface/conftest.py fixtures naming the owning rebuild task, legacy_only_* tests for behaviour the rebuild ends.
<!-- SECTION:NOTES:END -->
