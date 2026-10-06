---
id: TASK-139
title: >-
  Restructure the incident umbrella and scribe READMEs so developers can find
  where new incident work goes
status: To Do
assignee: []
created_date: '2026-10-06 15:56'
updated_date: '2026-10-06 16:23'
labels:
  - incident
  - docs
dependencies:
  - TASK-110.2
references:
  - app/packages/incident/scribe/README.md
  - decisions/incident-management.md
priority: medium
type: docs
ordinal: 318000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Colleagues find the scribe subdomain hard to read: the umbrella has no README; the sibling folders documents/, drive/, meet/ and scheduling/ hold adapters the ADR plans to absorb; scribe's naming still says draft/summary (settings INCIDENT_DRAFT__/INCIDENT_SUMMARY__, locale files, the incident_draft:: range prefix); its interfaces are split between core/api.py and scribe/service.py; and the 399-line README puts architecture last. Docs only: no renames, no code moves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/incident/README.md maps every folder of the umbrella with its current role and its target per decisions/incident-management.md, and has a 'where does new work go' table
- [ ] #2 scribe/README.md opens with an at-a-glance table per use case (command, service function, interfaces, adapters, settings prefix, locale files, tests), followed by the architecture section with one call-path diagram
- [ ] #3 scribe/README.md has an 'Adding a use case' checklist and a Naming note explaining the draft/summary names kept for env-var and catalogue stability
- [ ] #4 The existing draft and summarize behaviour detail is kept, under a Reference section; no code, settings or file names change
<!-- AC:END -->
