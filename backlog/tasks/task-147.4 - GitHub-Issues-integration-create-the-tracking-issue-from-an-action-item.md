---
id: TASK-147.4
title: 'GitHub Issues integration: create the tracking issue from an action item'
status: To Do
assignee: []
created_date: '2026-10-13 14:00'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
parent_task_id: TASK-147
priority: medium
type: feature
ordinal: 373000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/integrations/github/ client on the outbound-client contract, and a feature-owned adapter in postmortem/adapters/ behind a role-named Protocol that creates an issue from an action item and stores the reference. Repository selection and labels follow the design doc. An issue-tracking capability comes only when a second tracker (Trello, Jira) is needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An action item can create a GitHub issue and stores its reference with system and repository
- [ ] #2 The GitHub client is reached only from the adapter; import-linter keeps integrations out of the domain
<!-- AC:END -->
