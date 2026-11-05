---
id: TASK-145.6.2
title: >-
  IncidentReport in core/api.py with its Google Docs adapter on the gateway
  factories
status: To Do
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T00:44:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.6.1
parent_task_id: TASK-145.6
priority: medium
ordinal: 482000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12b of Stack K (TASK-145.6 plan, approved 2026-11-05). IncidentReport Protocol taking the record's ReportReference (create from template with a placement hint, placeholders, status text, timeline entry, read sections, draft copy, link), GoogleDocsIncidentReport over the moved functions, an in-memory fake. The Drive calls move from infrastructure.drive to the gateway's get_drive_service with pagination and shared-drive flags preserved, so the incident infrastructure.drive ignore entries are deleted (TASK-120 AC #2 lands here). No adapter passes a delegation subject or builds credentials (TASK-181 decides). Placement (OQ1): the report is filed in the child folder of folder_id named for the legacy product, else folder_id; this replaces modules/incident/core.py _find_product_folder and is report placement, not a catalogue. scribe's IncidentDocumentStore is replaced by IncidentReport. Subdomains using the report state folder_id and report_template_id as required on registration. The section writer's template labels move verbatim (OQ4). Legacy folder-admin and on-call metadata functions stay plain module functions off the Protocol (OQ2), deleted with modules/incident (TASK-145.13) and the on-call re-cut (TASK-146).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentReport is a Protocol in core/api.py whose methods take a ReportReference; GoogleDocsIncidentReport implements it and InMemoryIncidentReport is its fake, with a parity test
- [ ] #2 No incident module imports infrastructure.drive; the incident ignore entries for it are deleted from pyproject.toml
- [ ] #3 A test pins that the adapter calls the gateway factories with scopes only (no delegated_user_email) and that core/adapters imports no google.oauth2 or google.auth
- [ ] #4 The report is filed in the product-named child folder of folder_id when one matches, otherwise in folder_id; tests cover match, no match and no product
- [ ] #5 scribe uses IncidentReport from core.api; IncidentDocumentStore and get_incident_document_store no longer exist
- [ ] #6 With folder_id or report_template_id empty, a subdomain that uses the report fails boot with one plugin_boot_failed event naming the key
- [ ] #7 No user-visible command, reply or log event changes; the legacy_surface, scribe and comms suites pass
- [ ] #8 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline from the TASK-145.6 plan approved 2026-11-05 (steps 5-10, OQ1, OQ2, OQ4); full plan at pickup against 12a's code. Tests: test_incident_core_report_{create,placement,edits,sections,errors,fake_parity,no_delegation,settings_required}.py.
<!-- SECTION:PLAN:END -->
