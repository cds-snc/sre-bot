---
id: TASK-36.1
title: >-
  Pin the hard-coded legacy slash commands and interactions through the Bolt
  dispatch boundary
status: To Do
assignee: []
created_date: 2026-09-28 14:36
updated_date: '2026-10-23T17:09:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - decisions/transport-slack.md
  - https://github.com/cds-snc/sre-bot/issues/1611
parent_task_id: TASK-36
priority: high
ordinal: 285000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-36 pins only the 8 register_slack_commands hookimpls TASK-26.1 rewrites. The legacy surface registered through the hard-coded _register_legacy_handlers() list in app/server/lifespan.py (line 93) is not yet pinned: 6 slash commands (aws, talent-role, secret, atip and its alias aiprp, incident; /sre and /sre dev register through _register_legacy_slack_commands and are pinned by TASK-36) and 33 interactions (18 actions, 11 views, 4 events), 39 rows in all, as counted in the TASK-36 inventory (app/tests/integration/legacy_surface/INVENTORY.md).

Coordinator task. The pins are added in app/tests/integration/legacy_surface/ in four slices that reuse the TASK-36 harness: build a real slack_bolt App, register through the real startup step, drive it with App.dispatch(BoltRequest) and assert on ack, response and faked side effects only.
- TASK-36.1.1: harness extension (legacy-handler registration and action, view and event dispatch), the registration-set test for all 39 rows, and /incident, incident_view, incident_change_locale and handle_incident_action_buttons (gates TASK-145.7). 4 rows.
- TASK-36.1.2: the 16 incident_helper.py interactions (gates TASK-145.8 and TASK-145.9).
- TASK-36.1.3: aws, talent-role, secret, atip and aiprp with their 8 interactions (gates TASK-88 and TASK-39). 13 rows.
- TASK-36.1.4: the 6 webhook admin interactions (gates TASK-37.4). 6 rows.
These tests gate TASK-26.2 (runtime move) and the TASK-145, TASK-39 and TASK-88 surface rebuilds.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All four subtasks (TASK-36.1.1 to TASK-36.1.4) are done
- [ ] #2 Every hard-coded legacy slash command and interaction row of the TASK-36 inventory (6 commands, 33 interactions) has a pinning test driven through App.dispatch, or an explicit not-pinned reason with its owning ticket
- [ ] #3 The TASK-36 inventory marks each of the 39 rows pinned by the owning subtask
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposed at planning into TASK-36.1.1 to TASK-36.1.4 (see the description); the detailed plan is on TASK-36.1.1, the first slice. TASK-36.1.2 to .4 are re-grounded at pickup against the harness TASK-36.1.1 lands. Slice order: .1 (harness, registration set, declare group), then .2, .3 and .4 in any order. This task closes when all four are done and the inventory shows 39 pinned rows.
<!-- SECTION:PLAN:END -->
