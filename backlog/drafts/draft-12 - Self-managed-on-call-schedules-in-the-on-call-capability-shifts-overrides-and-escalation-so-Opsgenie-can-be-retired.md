---
id: DRAFT-12
title: >-
  Self-managed on-call schedules in the on-call capability: shifts, overrides
  and escalation, so Opsgenie can be retired
status: Draft
assignee: []
created_date: '2026-10-09 16:44'
labels:
  - oncall
  - capabilities
dependencies: []
priority: low
type: enhancement
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Optional enhancement, not scheduled. Opsgenie serves a small subset of teams, ends on 2027-04-05 and has no chosen replacement. The on-call capability (TASK-146) ships with two schedule sources, Opsgenie and self-managed weekly rotations. This draft grows the self-managed source into a schedule: shifts with start and end, overrides for a day or a shift, a handover notice, an escalation chain (who is next when the first person does not acknowledge), and Slack commands to view and change them. Paging itself (notifying the person) goes through the notifications capability and is a separate draft. Decide first whether the organisation adopts a replacement product; this is the fallback when none is adopted.
<!-- SECTION:DESCRIPTION:END -->
