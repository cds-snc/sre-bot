---
id: TASK-147.8
title: >-
  Postmortem rollout: internal comms package, permission policy and the flag
  flip
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-10-23T17:05:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
  - TASK-147.7
references:
  - https://github.com/cds-snc/sre-bot/issues/1713
parent_task_id: TASK-147
priority: medium
type: feature
ordinal: 377000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-led. The flip changes how people run a postmortem, so it ships with an internal comms package in EN and FR: what changes for responders and facilitators, how action items and GitHub issues work, who may capture timeline entries with the floppy-disk reaction, and the updated postmortem guidance. After the comms go out, the flag is turned on in app/config/production.toml through a reviewed PR and the production deploy workflow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The comms package and the updated postmortem guidance are published to internal users before the production flip
- [ ] #2 The flag is on in production and the capture-permission rule is the one announced
<!-- AC:END -->
