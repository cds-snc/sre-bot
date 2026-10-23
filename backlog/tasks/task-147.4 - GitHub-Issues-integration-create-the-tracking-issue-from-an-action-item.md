---
id: TASK-147.4
title: 'GitHub Issues integration: create the tracking issue from an action item'
status: To Do
assignee: []
created_date: 2026-10-13 14:00
updated_date: '2026-10-23T17:05:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-147.3
references:
  - https://github.com/cds-snc/sre-bot/issues/1709
parent_task_id: TASK-147
priority: medium
type: feature
ordinal: 373000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/integrations/github/ client on the outbound-client contract, available when its settings slice holds a tenant entry carrying the GitHub organisation (decisions/configuration.md: no GITHUB_ENABLED key; the credential read from the environment by the <SLICE>__<FIELD> rule), and a feature-owned adapter in postmortem/adapters/ behind a role-named Protocol that creates an issue from an action item and stores the reference. Repository selection and labels follow the design doc and are non-secret values in the configuration files. An issue-tracking capability comes only when a second tracker (Trello, Jira) is needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An action item can create a GitHub issue and stores its reference with system and repository
- [ ] #2 The GitHub client is reached only from the adapter; import-linter keeps integrations out of the domain
- [ ] #3 The GitHub client is available only when its slice holds a tenant entry; an absent entry boots with GitHub unconfigured and no network call
<!-- AC:END -->
