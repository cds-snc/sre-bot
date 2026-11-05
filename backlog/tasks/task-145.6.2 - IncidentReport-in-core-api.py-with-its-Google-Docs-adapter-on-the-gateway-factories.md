---
id: TASK-145.6.2
title: >-
  IncidentReport in core/api.py with its Google Docs adapter on the gateway
  factories
status: To Do
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T14:53:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.6.1
  - TASK-184
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
- [ ] #4 scribe uses IncidentReport from core.api; IncidentDocumentStore and get_incident_document_store no longer exist
- [ ] #5 With folder_id or report_template_id empty, a subdomain that uses the report fails boot with one plugin_boot_failed event naming the key
- [ ] #6 No user-visible command, reply or log event changes; the legacy_surface, scribe and comms suites pass
- [ ] #7 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [ ] #8 A new report is filed in [incident_core] folder_id; the Protocol takes no placement; legacy declare and recreate keep filing in the folder they pass (C2); empty folder_id or report_template_id returns CONFIG_NOT_CONFIGURED naming the key
- [x] #9 Before merge, a read-only count of incident items without report_url whose channel has an 'Incident report' bookmark is recorded in the notes; if not zero, the fallback decision (D1) is taken before merge
- [ ] #10 rg finds no IncidentReportLinkLookup, _DOC_ID_PATTERN or scribe/adapters/slack.py in app/; scribe resolves the incident with find_incident_for_conversation and takes the report from incident.report (C3)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Full plan 2026-11-05, grounded at main 5deb8406 + #1823 and the TASK-145.6.1 plan (post-move layout: features/incident/core/adapters/google_docs.py holds the documents utils, documents adapter, drive adapter and section writer verbatim). APPROVED 2026-11-05 (human), C1-C4 as recommended and D1 accept: corrections C1-C4 change the outline approved with the parent plan.

## Corrections to the approved outline (re-approval needed)
- C1 Protocol surface. The legacy status mapping (incident_document.py:55-80) and the timeline rewrite (:82-302, build_timeline_replacement alone ~118 lines of Docs batchUpdate requests) live in modules/incident, not in a feature adapter. Moving them now adds ~250 lines with no feature consumer until TASK-145.8 (status) and 145.9 (timeline). Recommended: IncidentReport in 12b has create_from_template, replace_placeholders, read_sections, write_draft_copy, link; set_status_text and append_timeline_entry are added by 145.8 and 145.9 when they rebuild those surfaces, moving the legacy code then. The ADR (incident-management.md:48) states the interface's end surface; no amendment needed.
- C2 Placement (refines OQ1). Declare passes the modal's folder id straight through (incident.py:134 -> core.py:492 create_incident_document); _find_product_folder (core.py:96-118) is used only by recreate_missing_resources (:378). The rebuilt declare ships without a product (incident-management.md 2026-11-04). Recommended: the Protocol takes no placement; the adapter files a new report in folder_id. Legacy declare and recreate keep calling the moved module functions with their folder, so today's filing in the product folder is unchanged (OQ1 kept). Placement returns, if needed, as report-placement configuration keyed by the bot's own product id (TASK-165.1). 145.6.2 AC #4 and the description are reworded accordingly.
- C3 The report link from the record moves here from 12c. Scribe finds the report today by the channel's "Incident report" bookmark (scribe/adapters/slack.py:24) and its own regex (scribe/service.py:173). IncidentReport takes a ReportReference, which scribe only has from the record. Recommended: 12b's scribe entry point builds the IncidentStore and resolves the incident with find_incident_for_conversation (the comms pattern, doc-13 2026-10-19) and passes incident.report; IncidentReportLinkLookup, scribe/adapters/slack.py, its provider and _DOC_ID_PATTERN are deleted here. 12c keeps the conversation interface and the reader by reference. Behaviour risk in the domain gate below (D1).
- C4 Required on register (AC #6 of the parent). The host resolves only workplace tenants and the openai, opsgenie, slack tables (server/plugins/requirements.py:31-41); Requirement("incident_core.folder_id") is unmet today, and listing a feature's table in host code inverts the layers. Recommended: a new small host task first (single PR from main, ~40 LOC + tests): a requirement on a table no vendor owns resolves against the settings slice the declaring plugin built (boot.built_slices(), the slice's toml_table_header), so a feature requires its own keys without the host knowing it. 12b then declares Requirement("incident_core.folder_id") and ("incident_core.report_template_id") in scribe's register_requirements (scribe/__init__.py:19-22); response declares them at 145.7. Alternative: drop the AC from 12b and give it to 145.7 (rejected: scribe uses the ids today).

## Steps (TDD: tests named below are written first and fail)
1. core/api.py: IncidentReport Protocol (role-named, feature-packages.md): create_from_template(title: str) -> OperationResult[ReportReference]; replace_placeholders(report: ReportReference, values: Mapping[str, str]) -> OperationResult[None]; read_sections(report) -> OperationResult[Sequence[DocumentSection]]; write_draft_copy(report, drafts, fields, links) -> OperationResult[DraftWriteResult]; link(report) -> str | None (the stored url, never formatted). DocumentSection, SectionDraft, DocumentField, DraftWriteResult move from scribe/domain.py to core/domain.py (scribe imports them from core.api). get_incident_report() provider (lru_cache, as get_incident_transcript_reader).
2. core/adapters/google_docs.py: class GoogleDocsIncidentReport implementing it over the moved functions; a reference of another system returns UNSUPPORTED_OPERATION; folder_id and report_template_id read at call time from get_incident_core_settings(); empty -> CONFIG_NOT_CONFIGURED naming the key.
3. Same module: the drive functions stop using infrastructure.drive. A private _drive() calls integrations.google_workspace get_drive_service(scopes=_DRIVE_SCOPES) with scopes only; a private _list_all(q) reproduces GoogleDriveProvider._list exactly (fields, pageSize=100, supportsAllDrives, includeItemsFromAllDrives, corpora="user", list_next paging, no page cap); create/copy keep supportsAllDrives=True; classify_google_error maps 429/5xx/404/401/403 as the provider did and unclassified statuses still raise; the module functions keep their return shapes (dict/None/[]) and failure logs (_log_failure), so legacy callers see no change. _DRIVE_SCOPES is a local constant (drive). find_files_by_name keeps the unescaped name (behaviour-preserving; a quote in a channel name already fails today; noted, not fixed).
4. pyproject.toml: delete the core adapter's ignore entries to infrastructure.drive, infrastructure.drive.factory, infrastructure.drive.models (renamed there by 145.6.1). No incident module imports infrastructure.drive (TASK-120 AC #2).
5. core/adapters/in_memory.py: InMemoryIncidentReport (stores created reports, placeholders applied, sections, draft copies; returns references for a test tenant; parity suite shared with the adapter).
6. scribe: ports.py loses IncidentDocumentStore and IncidentReportLinkLookup; providers.py loses get_incident_document_store and get_incident_report_link_lookup; service.py takes IncidentReport and the incident's ReportReference (:260, :286, :317, :319, :396 rewired; :173 _DOC_ID_PATTERN and :527 _find_report_document_id deleted); scribe/adapters/slack.py deleted; the scribe entry point (scribe/entrypoints/slack.py, as comms/entrypoints/slack.py:178-190 builds the store) resolves the incident through find_incident_for_conversation with the store from build_incident_store and replies as today when the channel is not an incident or the record has no report (i18n keys unchanged).
7. scribe/__init__.py register_requirements adds the two incident_core requirements (after C4's host task) (TASK-184, approved 2026-11-05; it must merge before this step). TASK-184 OQ1 (human, 2026-11-05): the CI configuration check is fixed here, not in TASK-184: tests/integration/server/test_server_plugins_configuration_requirements.py builds only the vendor slices, so extend it to build the incident_core slice (get_incident_core_settings, or the configuration phase) and supply placeholders for the env_only INCIDENT_CORE__FOLDER_ID and INCIDENT_CORE__REPORT_TEMPLATE_ID names, checked against terraform/ssm.tf or the Codespaces secrets per the plugins.md CI rule (TASK-175); production SSM must hold both values before merge (deploy-checks pre).
8. tests/integration/legacy_surface/conftest.py: the report-link patch (:49, :179) replaced by a seeded InMemoryIncidentStore with a report reference.

## Domain-model evolution gate
Entity reused: ReportReference {system, tenant, vendor_id = bare Doc id, url = stored link} (core/domain.py:159-186; the bridge sets it from report_url, legacy_items.py:239-247). No stored-shape change.
| Scenario | Record report | Before | After | Decision |
| --- | --- | --- | --- | --- |
| New incident with report | set | bookmark finds doc | record finds doc | same |
| Legacy item with report_url | from bridge | bookmark | record | same |
| D1 legacy item without report_url but a channel bookmark | None (bridge dropped) | draft works | "no report" reply | measure before merge; if any, keep a one-time bookmark fallback (rejected by default: guessing by channel breaks linked incidents) |
| Report_url not a Docs URL (dropped by the bridge) | None | regex fails too | "no report" | same outcome |
| Linked incidents (TASK-165.5), one report each | per record | first bookmark of that channel | that record's report | fixes a one-channel assumption |
| Report on a second suite | system != GOOGLE | n/a | UNSUPPORTED_OPERATION, logged | fail closed |
| Channel not an incident | n/a | "no report" | not-an-incident reply (comms wording) | check the reply key is unchanged; else keep today's |
AC added: before merge, a read-only count of incident items without report_url whose channel has an "Incident report" bookmark (D1); zero, or the fallback decision is taken.

## AC traceability (145.6.2 ACs, after rewording)
| AC | Steps | Tests |
| --- | --- | --- |
| 1 Protocol, adapter, fake, parity | 1, 2, 5 | test_incident_core_report_protocol_parity.py (fake and adapter over a stubbed service pass one behaviour suite) |
| 2 no infrastructure.drive | 3, 4 | lint-imports; test_incident_core_google_docs_drive.py (list paging over 2 pages, flags, Templates excluded, create, copy, find, 404/403/429 mapping, 400 raises) |
| 3 no subject, no credentials | 2, 3 | test_incident_core_report_no_delegation.py (factories called with scopes only; core/adapters imports no google.auth or google.oauth2) |
| 4 placement (reworded, C2) | 2 | test_incident_core_report_create.py (files in folder_id; empty folder_id or template id -> CONFIG_NOT_CONFIGURED naming the key); legacy test_incident_document.py unchanged |
| 5 scribe uses IncidentReport; store and lookup gone | 6, 8 | scribe service tests with InMemoryIncidentReport and InMemoryIncidentStore; rg IncidentDocumentStore and IncidentReportLinkLookup empty |
| 6 required on register | 7 | test_incident_scribe_requirements.py (empty key -> plugin_boot_failed naming it), after the C4 host task |
| 7 no visible change | all | legacy_surface, scribe, comms suites; the D1 count |
| 8 gates | all | ruff, targeted tests; at the end mypy then pytest once; lint-imports, make check-import-contracts, make check-settings-key-ownership |

## Size
Production: Protocol and moved types ~60, adapter class ~80, drive functions onto the gateway ~100 (net, provider calls replaced), scribe rewiring and entry-point resolution ~50 new, ~110 deleted (slack adapter, ports, providers, regex helpers), requirements ~5. ~295 new or changed, 9 production files (core/api.py, core/domain.py, core/adapters/google_docs.py, core/adapters/in_memory.py, scribe/domain.py, scribe/ports.py, scribe/providers.py, scribe/service.py, scribe/__init__.py, scribe/entrypoints/slack.py, pyproject.toml; scribe/adapters/slack.py deleted): 12 files, over the ~10-file guide only by one-line edits (domain types move, ignores). Gate passes with C1; without C1 it would be ~550.

## Assumptions and doubts
- Retries stay where they are: the gateway's request builder (client.py:95); the provider added none.
- appProperties stay readable: same service account and OAuth client; this layer does not change who calls run as (tenant default delegation until TASK-181).
- The scribe entry point can build the IncidentStore the way comms does; verify against comms' entry point at pickup.
- D1 count: production is read-only from local AWS; the human runs the scan (command given at handoff).

## Blast radius and rollback
A defect breaks /incident draft (scribe) or legacy report creation and folder listing on declare; caught by the drive tests and legacy_surface. One revert restores both (no data written differently, no settings change). No terraform, IAM, SSM or env change: no deploy-checks. If C4's host task (TASK-184) is not merged yet, step 7 waits and AC 6 stays open; nothing else depends on it.

AC numbering in the task after the rewording: plan rows 1-3 = ACs #1-#3, 5 = #4, 6 = #5, 7 = #6, 8 = #7, 4 = #8; the D1 count is #9.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-05 D1 count (human, read-only scan of incidents): 2 of 330 items have no report_url (missing or empty). Not yet known whether their channels hold an 'Incident report' bookmark, nor their status and age; the D1 decision (fallback or accept) waits on that, before merge (AC #9 stays open).

2026-11-05 D1 identified (human scan): the 2 items without report_url are test incidents, both status Open: 4137a21d-75b4-4dc0-b5be-fe52985d6e0a ('Test New conversation Creation', channel incident-dev-2025-08-25-test-new-conversation-creation) and 827e5751-3b84-4eba-bc8a-54f3d8c3f2b2 ('2026-05-05-test-incident'). Proposed D1 decision: accept, no bookmark fallback and no backfill; /incident draft there answers 'no report'. AC #9 is checked when the plan (C1-C4, D1) is approved.

2026-11-05 (human): plan approved with C1-C4 as recommended. C1: set_status_text and append_timeline_entry are added by TASK-145.8 and 145.9 (recorded there). C2: the Protocol takes no placement; legacy filing unchanged. C3: the report link from the record and the IncidentReportLinkLookup deletion are here (AC #10, moved from TASK-145.6.3 old AC #4). C4: host task TASK-184 (requirements resolve a feature's own settings table) created as a dependency; AC #5 waits on it.
2026-11-05 D1 decided (human): accept. The 2 items without report_url are open test incidents; no bookmark fallback, no backfill; /incident draft there answers 'no report'. AC #9 checked.

2026-11-05 handoff from the TASK-184 plan: tests/integration/server/test_server_plugins_configuration_requirements.py builds only the vendor slices (lines 40-48), so once scribe declares incident_core.folder_id and report_template_id (AC #5) that production/local configuration check reports them unmet unless it also builds get_incident_core_settings (and supplies placeholders for any env_only names). Fold into step 7 at TDD.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T01:03:00Z

---

2026-11-05 full plan, proposed: corrections C1 (status text and timeline entry join with 145.8/145.9), C2 (no placement on the Protocol; legacy filing unchanged), C3 (the report from the record and IncidentReportLinkLookup deletion move here from 145.6.3), C4 (new host task: requirements resolve a feature's own settings table; AC #6 waits on it). AC #4 (product-folder placement) replaced by the new AC on folder_id (renumbered), AC for the D1 count added. Awaiting approval.

---
<!-- COMMENTS:END -->
