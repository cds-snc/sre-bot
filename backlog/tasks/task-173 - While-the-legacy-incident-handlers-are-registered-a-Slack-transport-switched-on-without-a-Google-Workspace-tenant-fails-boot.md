---
id: TASK-173
title: >-
  While the legacy incident handlers are registered, a Slack transport switched
  on without a Google Workspace tenant fails boot
status: To Do
assignee: []
created_date: '2026-10-27T18:11:00Z'
labels:
  - configuration
  - plugins
milestone: m-7
dependencies:
  - TASK-111.10.2
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
priority: medium
ordinal: 454000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/configuration.md (Tolerated, 2026-10-27): the legacy incident code in modules/ needs Google Workspace (documents, Drive, calendar) and is not a plugin, so it cannot state a requirement itself (decisions/plugins.md). Until the incident rebuild's declare path states its own requirement (Stack M, TASK-145.7 AC #9), the host does it: in the configuration phase, a Slack transport switched on with no Google Workspace tenant entry fails boot naming GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID, as a transport switched on without its own vendor's tenant entry already does (decisions/lifecycle.md phase 1). No ENVIRONMENT comparison. Deleted with the legacy incident handlers.

TODAY: CI and a Codespace without a Google tenant boot and fail at use; production configures the tenant (TASK-111.10.2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With [slack_transport] enabled and no Google Workspace tenant entry, boot fails in the configuration phase naming GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID; with the transport off, or with a tenant, boot succeeds (tests)
- [ ] #2 The rule sits beside the existing transport-requires-vendor check, carries a comment naming the legacy incident handlers it exists for, and is listed in decisions/configuration.md Tolerated
- [ ] #3 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->
