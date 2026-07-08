---
id: TASK-36
title: Build the smoke-test harness for the legacy Slack command and webhook surface
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - migration
  - phase-5
  - testing
milestone: m-5
dependencies: []
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1290'
priority: high
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/migration.md recipe step 1: capture the external compatibility contract (Slack command surface + webhook URLs) BEFORE touching any module. Other teams depend on this surface.

Steps:
1. Inventory every Slack command, action, and webhook route exposed by app/modules/ (13 module groups; grep registration sites + _register_legacy_handlers()). Record the inventory as a checked-in table (app/tests/smoke/legacy_surface.md or a YAML fixture).
2. Write smoke tests that exercise each command/webhook through the transport boundary (Bolt test client / ASGI TestClient) asserting: command acknowledged, response shape/text, side-effect stub invoked. Use fakes for backing services - the contract under test is the surface, not the vendor.
3. Mark as smoke layer per decisions/testing.md (on-demand + pre/post each module cutover; not the PR gate).
4. These tests are the pass/fail oracle for every task-37..40 cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A checked-in inventory lists every legacy command/action/webhook with its owning module
- [ ] #2 Each inventoried surface has at least one smoke test that passes against current main
- [ ] #3 Runbook note: how to run the suite pre- and post-cutover for a module
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Suite green on main
- [ ] #2 PR references decisions/migration.md recipe step 1
<!-- DOD:END -->
