---
id: TASK-146.1
title: >-
  Build app/capabilities/oncall: schedules, rotations and who is on call now,
  with Opsgenie and self-managed sources
status: To Do
assignee: []
created_date: '2026-10-09 16:44'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-25.6
  - TASK-114
parent_task_id: TASK-146
priority: medium
type: feature
ordinal: 365000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 1 of TASK-146. decisions/oncall.md and plugin-architecture.md: a capability's public surface is api.py.

THIS SLICE
- capabilities/oncall/api.py: OnCallLookup Protocol (who is on call for a schedule reference now; the schedule's members), domain types Schedule, Rotation, Shift, OnCallPerson (a person reference as decisions/people-and-accounts.md defines it today), ScheduleReference carrying system and id, and the provider function. README states the classification (generic) and the consumers (oncall_sync, incident).
- domain.py and service.py: the self-managed rotation logic from packages/user_rotations (weekly rotation, weeks per shift, members) as the "rotations" schedule source, selected by the reference's system, never by a setting.
- adapters/opsgenie.py: the Opsgenie schedule reads from packages/oncall_sync/adapters/opsgenie.py over the TASK-25.6 client, the only importer of integrations.opsgenie; README notes the vendor's end date. adapters/rotations.py: the JSON rotation files. An in-memory fake.
- entrypoints/slack.py: user_rotations' Slack commands, renamed from platforms/ and made to call one service method each.
- Entry point and enablement key; packages/user_rotations is deleted and every importer rewritten (oncall_sync's import is replaced in TASK-146.2 in the same stack, or temporarily points at the capability's api).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 capabilities/oncall/api.py exposes OnCallLookup, the domain types and the provider; nothing else in the package is imported from outside
- [ ] #2 Both schedule sources are selected by the reference's system; the in-memory fake covers both
- [ ] #3 integrations.opsgenie is imported only by capabilities/oncall/adapters/opsgenie.py
- [ ] #4 packages/user_rotations no longer exists and no vocabulary from incident or oncall_sync appears in the capability
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
