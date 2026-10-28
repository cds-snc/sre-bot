---
id: TASK-174
title: >-
  Microsoft Entra ID directory adapter in capabilities/directory, resolved by
  the IdP in the data
status: To Do
assignee: []
created_date: '2026-10-28T14:14:00Z'
labels:
  - workplace-systems
  - capabilities
dependencies:
  - TASK-119
references:
  - decisions/authorization.md
  - decisions/people-and-accounts.md
  - decisions/workplace-systems.md
  - decisions/configuration.md
priority: low
type: feature
ordinal: 458000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Unscheduled; build when Entra becomes a trusted IdP, beside Google or instead of it (the same trigger as TASK-83.13). Found 2026-10-28 in TASK-111.13.1, which deleted the DIRECTORY_PROVIDER switch: its entra_id value had no implementation (the factory raised), and a one-value switch cannot serve Google and Entra at once, which the ADRs require (authorization.md: 'or both at once'; people-and-accounts.md: each trusted IdP is an (idp, tenant) pair, several without change; workplace-systems.md: which system serves an operation is data). The vendor-neutral DirectoryProvider Protocol is the extension point: TASK-119 moves it to capabilities/directory/ with one adapter per system in adapters/. This task adds the Entra adapter (membership through Microsoft Graph checkMemberGroups, authorization.md), the Entra vendor slice whose tenant entry (the tenant id, a GUID per workplace-systems.md format rules, and credentials) makes Entra available, and resolution of the adapter from the idp of the reference being looked up instead of one deployment-wide provider. Planning inputs: the credential model and minimum Graph permissions follow the TASK-169 ruling for Google (least privilege per caller, keyless federation where possible); Entra users as people are TASK-83.13.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An Entra adapter implements the directory capability's Protocol, reading group membership through Microsoft Graph (checkMemberGroups), with an in-memory fake covering the same contract
- [ ] #2 Entra is available exactly when its vendor slice holds a tenant entry (tenant id checked as a GUID, credentials as secrets); there is no provider or enabled setting
- [ ] #3 The directory capability resolves the adapter from the idp and tenant of the reference it is asked about, so Google and Entra answer side by side; a reference to an IdP with no tenant entry fails with a classified error, not a fallback to another IdP
- [ ] #4 decisions/authorization.md, people-and-accounts.md and workplace-systems.md record the adapter and how it is selected
- [ ] #5 ruff, mypy (no new errors), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->
