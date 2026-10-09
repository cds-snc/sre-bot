---
id: TASK-146
title: >-
  On-call as a capability: who is on call now, from Opsgenie or self-managed
  schedules; oncall_sync becomes its feature consumer
status: To Do
assignee: []
created_date: '2026-10-09 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - oncall
  - capabilities
  - plugin-architecture
dependencies: []
references:
  - decisions/oncall.md
  - decisions/plugin-architecture.md
priority: medium
type: feature
ordinal: 364000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. Supersedes TASK-123 (user rotations as a rotations capability) and TASK-124.2 (move oncall_sync), which stay as history with a pointer here.

DIRECTION (human, 2026-10-09): "who is on call for this schedule right now" is a capability: its vocabulary is free of any feature, two features need it (incident at declare, the Slack usergroup sync) and a vendor sits behind it. Self-managed rotations are one schedule source among others, not a capability of their own. Opsgenie is used by a small subset of teams, is being retired by its vendor (service ends 2027-04-05) and no replacement has been chosen; the capability must work with the self-managed source alone, and self-managed schedules (shifts, overrides, escalation) are the likely successor, recorded as an optional enhancement (a draft), not scheduled. Paging, meaning notifying the person on call, is a separate concern for the notifications capability. decisions/oncall.md holds the decision; this task holds the breakdown.

STARTING POINT (2026-10-09): packages/oncall_sync reads Opsgenie schedules and self-managed rotations and writes Slack usergroups every five minutes; it imports packages.user_rotations in three places, a feature-to-feature import. packages/user_rotations holds the self-managed rotation logic (one JSON file per rotation) with Slack handlers under platforms/. The incident declare flow invites on-call people from the product catalog's Opsgenie schedule reference.

ASSUMPTIONS IN FORCE:
- the capability lives in app/capabilities/oncall/ in the feature-packages shape once the capabilities directory exists (after TASK-114, as the other capability moves);
- the Opsgenie adapter is built after TASK-25.6 brings Opsgenie onto the outbound-client contract, and is marked as ending on 2027-04-05 in its README;
- user_rotations' Slack commands stay with the capability as its entry points (a capability may expose its own API surface), renamed to entrypoints/;
- oncall_sync stays a feature: projecting who is on call into Slack usergroups is organisation-specific configuration (rotations.json) over a workplace system, with the user token per decisions/service-accounts.md.

LAYERS, each a single PR under the size gate: TASK-146.1 (the capability, with both schedule sources and a fake) -> TASK-146.2 (oncall_sync consumes it and moves to features/) ; TASK-146.3 (incident declare invites through the capability) after TASK-146.1 and TASK-145.7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every subtask is done
<!-- AC:END -->
