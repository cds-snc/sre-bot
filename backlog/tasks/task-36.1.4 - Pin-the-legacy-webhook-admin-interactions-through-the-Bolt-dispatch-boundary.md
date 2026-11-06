---
id: TASK-36.1.4
title: Pin the legacy webhook admin interactions through the Bolt dispatch boundary
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
  - https://github.com/cds-snc/sre-bot/issues/1741
parent_task_id: TASK-36.1
priority: low
ordinal: 398000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fourth slice of TASK-36.1, reusing the harness from the first slice. Pins the 6 modules/sre/webhook_helper.py interactions TASK-37.4 replaces: view create_webhooks_view; actions toggle_webhook, reveal_webhook, next_page, channel (ack only), hook_type (ack only).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 6 interaction rows has a dispatch-driven test covering ack, Slack-visible calls and faked webhook store side effects
- [ ] #2 INVENTORY.md marks these rows pinned by this task
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Pin task: durable entry points, modal ids read from the opened view, outcome assertions at faked external edges, internal legacy seams only in named legacy_surface/conftest.py fixtures naming the owning rebuild task, legacy_only_* tests for behaviour the rebuild ends.
<!-- SECTION:NOTES:END -->
