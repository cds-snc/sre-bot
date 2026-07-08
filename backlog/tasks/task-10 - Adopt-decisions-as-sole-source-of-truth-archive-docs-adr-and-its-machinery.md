---
id: TASK-10
title: Adopt decisions/ as sole source of truth; archive docs/adr/ and its machinery
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies: []
references:
  - decisions/governance.md
  - decisions/README.md
priority: high
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/governance.md. decisions/*.md supersedes docs/adr/ (44 records). docs/adr/ stays for history but must stop looking authoritative.

Steps:
1. Add a prominent banner to docs/adr/ (a README at docs/adr/README.md): superseded by /decisions, do not update, kept for history.
2. Delete or archive the ADR index machinery tied to docs/adr/: .github/scripts/generate_adr_indexes.py, the stale INDEX.md generation flow, and the invalid-YAML template under docs/adr/templates/ (they are wired into no workflow today - confirm before deleting).
3. Ensure the repo README (and CONTRIBUTING if present) points contributors at decisions/README.md reading order.
4. Do not edit the historical ADR contents themselves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/adr/README.md exists and states the supersession; repo README links to decisions/
- [ ] #2 No script or workflow generates or validates docs/adr/ indexes anymore
- [ ] #3 git log shows no further commits touching docs/adr/*.md content after this PR (process expectation recorded in the banner)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR merged with reviewer sign-off on what was archived vs deleted
- [ ] #2 PR references decisions/governance.md
<!-- DOD:END -->
