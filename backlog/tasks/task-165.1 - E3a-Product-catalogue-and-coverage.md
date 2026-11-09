---
id: TASK-165.1
title: >-
  Product catalogue: the bot's own product list as the default source, an
  optional Backstage adapter, and a coverage report
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-09T19:04:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-145.6
references:
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 462000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The bot must run standalone: its product catalogue's default source is a product list the bot holds (provisioned content or managed records, per decisions/organisation-content.md; this epic decides which), as no workplace system is a dependency (human, 2026-11-05, TASK-145.6 re-plan). The incident feature needs a stable catalogue contract for products, owner-group identifiers and repositories; the record's product id is the bot's own. Backstage is the organisation's larger catalogue: an optional adapter that may delegate to it when an instance configures it, never required; the catalog-info.yml clean-up across repositories is not a precondition. The organisation also needs a coverage report to reveal repositories that are absent from the catalogue. First run the D28-D32 decision session and record its outcome in decisions/product-catalog.md; keep group-to-person resolution out of this epic until D33 is decided.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The D28–D32 decisions are recorded in decisions/product-catalog.md, covering product and repository ownership, unowned repositories, tracking-issue confidentiality, and coverage.
- [ ] #2 A repeatable organisation-wide coverage report identifies catalogue gaps by repository and owner group and provides a metric/reminder path for the resulting clean-up.
- [ ] #3 Tests and documentation verify the catalogue contract, adapter behavior, and coverage output; the epic is not closed before the report runs.
- [ ] #4 The approved task plan retains the reviewed scenario/cardinality matrix from the domain-model-evolution skill: multiple repositories per product, shared dependencies, missing owners and products without repositories. The ADR records ownership and relationship invariants, with contractual fields only; tests cover the catalogue behavior introduced here.
- [ ] #5 A ProductCatalog contract with a default adapter over the bot's own product list provides products, owner-group identifiers, repositories for a product, and owner lookup for a repository, with no external catalogue configured; an optional Backstage adapter serves the same contract; owner-group identifiers are not expanded into people
- [ ] #6 A test boots the incident feature with no external catalogue configured and lists products from the bot's own source
- [ ] #7 Before TASK-145.13 deletes modules/incident, a one-off import carries each product Drive folder's genie_schedule into the bot's product list as the product's ScheduleReference; the folder-to-product mapping is confirmed by a human (a report-placement folder is not a product), every other appProperties key is listed for a human ruling and none is dropped silently; the plan settles schedules per product (legacy 0..1) against the scenarios recorded in TASK-36.1.2 OQ5
- [ ] #8 The one-off genie_schedule import replaces the incident schedule-source adapter (TASK-146.3, delivered in TASK-145.7) with the catalogue entry and deletes its tolerated line; the Notify management invite trigger moves from [incident_response] notify_management_placement_id to the product id
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved, coordinated-incidents reconciliation): the incident record keeps an optional product meaning one product's response (incident-management.md 2026-11-04). This task defines its identifier (a product-catalogue id) and builds the ProductCatalog port in features/incident/core with its catalogue adapter (Backstage); TASK-145.6 no longer builds one over Drive folders. A product is not a team: teams own products many-to-many. Legacy stored items carry teams (a Drive folder name list) as a legacy attribute; nothing maps it to a product or infers engagements from it (D33). Adding product to declare (TASK-145.7 ships without it) is part of this task's consumer work or a follow-up it names.

2026-11-06 (TASK-36.1.2 OQ5, human-approved): depends on TASK-145.6 (core, where ProductCatalog lives) instead of all of TASK-145, and gates TASK-145.13, so the legacy schedule source (on_call.py, folder metadata) is not deleted before the product list holds the references. Scenarios for the plan: one schedule; none (declare invites nobody and says so); unknown metadata keys; self-managed rotation or after the Opsgenie end of service 2027-04-05 (system-typed reference, TASK-146.3); coordinated incident engaging many products; one schedule shared by several products; a folder that is report placement only.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T00:43:00Z

---

2026-11-05 (human, TASK-145.6 re-plan): the bot runs standalone; the default catalogue source is the bot's own product list, Backstage an optional adapter. AC #2 (Backstage adapter) replaced by AC #6 and #7. decisions/incident-management.md and organisation-content.md amended.

---

created: 2026-11-05T00:43:00Z

---

Correction to the previous comment: the replacements are AC #5 and #6 (renumbered after the removal).

---

created: 2026-11-09T18:37:00Z

---

Stack L OQ assessment 2026-11-09 (OQ1, OQ2, OQ12), proposed scope: the one-off genie_schedule import replaces the incident schedule-source adapter (TASK-146.3 in 145.7 L9a) with the catalogue entry and deletes its tolerated line; the Notify management invite trigger moves from [incident_response] notify_management_placement_id to the product id. AC #7 ('a report-placement folder is not a product') holds.

---
<!-- COMMENTS:END -->
