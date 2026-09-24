---
id: TASK-36
title: Build the smoke-test harness for the legacy Slack command and webhook surface
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:05'
labels:
  - migration
  - phase-5
  - testing
milestone: m-5
dependencies: []
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1290'
  - decisions/plugin-architecture.md
priority: high
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24. decisions/migration.md step 1 (Inventory) now asks for more than a smoke-test list: every user-facing surface of modules/ (slash commands and subcommands, interactions, webhook routes, HTTP routes under app/api/, and scheduled jobs in app/jobs/) is listed with a target feature or capability, so each rebuild ticket knows where its surface lands. Surfaces are assigned by what they do, not by which module holds them today: modules/sre and modules/aws are grab-bags, and incident surfaces follow the TASK-97 decision.

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
- [ ] #4 The checked-in inventory assigns every surface (commands, interactions, webhook and HTTP routes, scheduled jobs) a target feature under app/features/ or capability under app/capabilities/, or marks it for deletion with the reason
- [ ] #5 The inventory records, per surface, the rebuild ticket that owns it (TASK-37, TASK-38, TASK-39, TASK-40, TASK-88, TASK-52/TASK-65 for jobs, TASK-53 for app/api/ routes)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Suite green on main
- [ ] #2 PR references decisions/migration.md recipe step 1
<!-- DOD:END -->
