---
id: TASK-12
title: >-
  Record the two open policy deltas: dependency-scanning gate ownership and
  hookspec deprecation lifecycle
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies:
  - TASK-10
references:
  - decisions/governance.md
  - decisions/plugins.md
priority: low
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-REVIEW-AND-MIGRATION-PLAN.md par.8 lists two gaps the new corpus left open:
1. Dependency scanning: Renovate exists, but no record states who owns the quality gate (does a vulnerable-dep finding block CI? who triages?).
2. Hookspec versioning/deprecation: deprecation-by-docstring exists but no lifecycle rule (how long a deprecated hookspec lives, how removal is announced).

Steps:
1. Write each as a short decision record in decisions/ following decisions/governance.md format (four frontmatter fields, two pages max, executable Checks).
2. For dependency scanning, decide: advisory vs blocking, and the triage owner.
3. For hookspecs, decide: deprecation marker, minimum deprecation window, and the removal checklist (grep for implementers before delete).
4. Update decisions/README.md index (governance check: index matches folder).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two new records exist in decisions/ with status Accepted and honest applies values
- [ ] #2 decisions/README.md index lists both
- [ ] #3 Each record has Checks that a CI step or five-minute review can verify
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR merged following the cascade rule (grep for references, none dangling)
<!-- DOD:END -->
