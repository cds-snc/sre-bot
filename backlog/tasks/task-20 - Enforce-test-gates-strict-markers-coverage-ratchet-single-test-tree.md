---
id: TASK-20
title: 'Enforce test gates: strict markers, coverage ratchet, single test tree'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - toolchain
  - phase-2
  - testing
milestone: m-2
dependencies:
  - TASK-18
references:
  - decisions/testing.md
  - 'https://github.com/cds-snc/sre-bot/issues/1274'
priority: medium
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/testing.md (Gates, One tree). Today: no --strict-markers, slow marker unregistered, coverage advisory with no fail_under, and a second root-level tests/architecture/ tree sits outside CI asserting a contract the decisions have since changed.

Steps:
1. pyproject addopts: --strict-markers; register unit/integration/smoke/slow/legacy markers.
2. Measure current coverage; set fail_under to that value (never lower it; raise as it climbs).
3. Move root tests/architecture/ into app/tests/ (or delete tests made redundant by task-18 import-linter contracts - most of it is superseded); update any that assert the OLD client contract to assert the decided one (clients raise; adapters classify).
4. Ensure the smoke layer stays out of the PR gate; slow marker excludes DynamoDB-Local tests from the default run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 pytest fails on an unregistered marker (strict-markers active)
- [ ] #2 Coverage fail_under set at the measured value and blocking in CI
- [ ] #3 No root-level tests/ tree exists outside app/tests/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI green with the gates active
- [ ] #2 PR references decisions/testing.md
<!-- DOD:END -->
