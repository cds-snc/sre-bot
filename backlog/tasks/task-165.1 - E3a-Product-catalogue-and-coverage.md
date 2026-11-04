---
id: TASK-165.1
title: E3a Product catalogue and coverage
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-04T17:26:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-145
references:
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 462000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Backstage is the organisation's source for product ownership, but the incident feature needs a stable catalogue contract for products, owner-group identifiers and repositories. The organisation also needs a coverage report to reveal repositories that are absent from the catalogue. First run the D28–D32 decision session and record its outcome in decisions/product-catalog.md; keep group-to-person resolution out of this epic until D33 is decided.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The D28–D32 decisions are recorded in decisions/product-catalog.md, covering product and repository ownership, unowned repositories, tracking-issue confidentiality, and coverage.
- [ ] #2 A ProductCatalog contract and Backstage adapter provide products, owner-group identifiers, repositories for a product, and owner lookup for a repository; owner-group identifiers are not expanded into people.
- [ ] #3 A repeatable organisation-wide coverage report identifies catalogue gaps by repository and owner group and provides a metric/reminder path for the resulting clean-up.
- [ ] #4 Tests and documentation verify the catalogue contract, adapter behavior, and coverage output; the epic is not closed before the report runs.
- [ ] #5 The approved task plan retains the reviewed scenario/cardinality matrix from the domain-model-evolution skill: multiple repositories per product, shared dependencies, missing owners and products without repositories. The ADR records ownership and relationship invariants, with contractual fields only; tests cover the catalogue behavior introduced here.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved, coordinated-incidents reconciliation): the incident record keeps an optional product meaning one product's response (incident-management.md 2026-11-04). This task defines its identifier (a product-catalogue id) and builds the ProductCatalog port in features/incident/core with its catalogue adapter (Backstage); TASK-145.6 no longer builds one over Drive folders. A product is not a team: teams own products many-to-many. Legacy stored items carry teams (a Drive folder name list) as a legacy attribute; nothing maps it to a product or infers engagements from it (D33). Adding product to declare (TASK-145.7 ships without it) is part of this task's consumer work or a follow-up it names.
<!-- SECTION:NOTES:END -->
