---
id: TASK-145.8.5.2
title: 'Slack transport: legacy attachment aliases scoped to button values'
status: To Do
assignee: []
created_date: '2026-11-16T19:34:00Z'
labels:
  - slack
  - transport
dependencies: []
references:
  - decisions/transport-slack.md
parent_task_id: TASK-145.8.5
priority: medium
type: feature
ordinal: 524000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L side PR from main (doc-11 row 18.L7a.2), no consumer (dark). Created 2026-11-16 (human, TASK-145.8.5 OQ3). One posted legacy attachment callback can carry buttons owned by different listeners (archive_channel: archive by incident.response, ignore by TASK-145.9.2, schedule_retro by incident.postmortem, TASK-36.1.2 ruling), and rebuilt listeners attach before the legacy ones, so a plain alias would take every button. register_attachment_action takes aliases scoped to action values; the provider attaches each with a value matcher (Bolt runs the first listener whose matchers pass), so an unclaimed value falls through to a later legacy listener. New messages carry one Block Kit action id per button. TASK-145.13 removes the aliases.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 register_attachment_action accepts legacy callback aliases scoped to action values; the provider attaches each scoped alias with a value matcher so an unclaimed value reaches a listener registered later; a value claimed twice for one callback aborts boot; the provider's alias listing names the values
- [ ] #2 decisions/transport-slack.md amended (value-scoped aliases; new messages carry one Block Kit action id per owning listener; TASK-145.13 removes them) with sources and a dated Changes line
- [ ] #3 Tests: a claimed value reaches the rebuilt listener, an unclaimed value reaches a legacy listener registered after it, a duplicate claim aborts boot, unscoped aliases behave as before
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
