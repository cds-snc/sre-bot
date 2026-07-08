---
id: TASK-32
title: 'Resolve the empty infrastructure services: persistence/ and notifications/'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - infrastructure
  - phase-4
milestone: m-4
dependencies: []
references:
  - decisions/layers.md
priority: low
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/infrastructure/persistence/ is empty (0 files) and app/infrastructure/notifications/ is a README saying "to be rebuilt". Empty services make the "composed services behind Protocols" claim false and confuse contributors.

Steps:
1. For each: decide with the maintainer - build it now (only if a concrete consumer exists), or delete the directory and record the deletion rationale in the PR (it can be recreated when a real consumer appears, per the second-consumer promotion rule in decisions/layers.md).
2. Default recommendation: delete both; storage covers persistence needs today and notifications has no consumer.
3. Also declare which infrastructure services are deliberately Protocol-less framework concerns (logging, plugins, configuration) in decisions/layers.md or a README, so the Protocol-coverage claim is honest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Neither an empty package nor a README-only package exists under app/infrastructure/
- [ ] #2 A one-paragraph note records which services are deliberately Protocol-less and why
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR merged with maintainer sign-off on the delete-vs-build choice
<!-- DOD:END -->
