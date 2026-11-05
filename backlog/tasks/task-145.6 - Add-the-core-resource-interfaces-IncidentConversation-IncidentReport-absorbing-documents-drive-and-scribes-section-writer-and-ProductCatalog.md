---
id: TASK-145.6
title: >-
  Add the core resource interfaces IncidentConversation and IncidentReport
  (absorbing documents/, drive/ and scribe's section writer)
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-05T00:44:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.5
  - TASK-145.5.8
  - TASK-111.10
references:
  - https://github.com/cds-snc/sre-bot/issues/1697
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 356000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12 of Stack K (TASK-145). decisions/incident-management.md: core/ holds the resource interfaces with two or more subdomain consumers, one adapter per system in core/adapters/, selected by the stored reference. Behaviour-preserving. Coordinator of TASK-145.6.1 (move), 145.6.2 (IncidentReport), 145.6.3 (IncidentConversation and the reader).

THIS SLICE
- IncidentConversation (core/api.py): post a message, set the purpose, add a bookmark, invite people, archive, report writability. Slack adapter in core/adapters/slack.py beside the transcript reader.
- IncidentReport (core/api.py): create from a template, replace placeholders, set the status text, append a timeline entry, read sections, write a draft copy with filled sections, return the link. One Google adapter in core/adapters/google_docs.py absorbing features/incident/documents, features/incident/drive and scribe/adapters/google_docs.py (the section writer), so the umbrella has one Google Docs adapter; the three sources are deleted and every importer, including modules/incident, is repointed (migration.md rule 5).
- IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe and comms resolve the incident through find_incident_for_conversation and pass the record's reference. IncidentReportLinkLookup is deleted: the report reference comes from the record.
- Templates and Google resource ids are read inside the adapters, never at import time. The umbrella layers contract drops documents and drive.
- Out of scope: ProductCatalog (TASK-165.1; the bot's own product list as its default source, 2026-11-05).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/documents, features/incident/drive and scribe/adapters/google_docs.py are deleted; core/adapters/google_docs.py is the only Google Docs adapter in the umbrella
- [ ] #2 IncidentTranscriptReader takes a ConversationReference; IncidentReportLinkLookup no longer exists
- [ ] #3 No user-visible command, reply or log event changes; the legacy_surface suite and the scribe and comms tests pass
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 The core reads the incident folder and report template ids from [incident_core] (folder_id, report_template_id) and each subdomain that uses them states it as required when it registers (decisions/plugins.md: a plugin states what it requires by resolving it; boot fails naming the key when it is empty). The key itself is already in place (TASK-111.10.3: non-public, declared empty in base.toml, value from the environment only)
- [ ] #6 Its Google adapters build services through integrations/google_workspace without passing a delegation subject or building credentials; which calls delegate is the gateway's (TASK-181; decisions/service-accounts.md rule 5)
- [ ] #7 IncidentConversation and IncidentReport are Protocols in core/api.py with one adapter each in core/adapters/ and in-memory fakes; ProductCatalog is TASK-165.1's
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-plan 2026-11-05, grounded at main 5deb8406 with Stack K #1821 (11b) and #1822 (11c) open below it. Replaces the 2026-10-09 plan. PROPOSED, awaiting human approval. ProductCatalog is out of scope (option C, 2026-11-04); TASK-169 D6 applies (AC #7).

## Size gate: trips, split proposed into three layers
Unsplit: ~1,600 moved lines (documents/ 157, scribe/adapters/google_docs.py 1,415, drive/ 147), ~25 production files, two Protocols with new adapters, and a mechanical move mixed with new behaviour-bearing code. CLAUDE.md requires the split. Each layer below passes alone.

| Layer | Task | Kind | Prod files | Prod LOC (new/changed) |
| --- | --- | --- | --- | --- |
| 12a | TASK-145.6.1 move the three Google sources into core/adapters/google_docs.py | mechanical only | ~16 (most one-line import repoints) | ~1,600 moved, ~40 changed |
| 12b | TASK-145.6.2 IncidentReport Protocol and its adapter on the gateway factories | new port, behaviour-preserving | ~8 | ~320 |
| 12c | TASK-145.6.3 IncidentConversation, writability, reader takes a ConversationReference, link lookup deleted | new port, behaviour-preserving | ~9 | ~380 |

Order: 12a above #1822 (11c), so #1822 may merge once 12a is submitted (doc-13 rule). 12b above 12a; 12c above 12b (12c touches scribe/service.py, which 12b also edits). The parent keeps every AC; each subtask carries its own.

## Discovered state (call sites)
- core/api.py (159): only IncidentTranscriptReader (:79; conversation_started_at(conversation_id: str) :87, read_transcript :96); get_incident_transcript_reader lru_cache :145; find_incident_for_conversation :151. Providers are plain functions, not svcs. #1821 also edits core/api.py, common/settings.py, base.toml and tests/unit/features/incident/core/test_incident_core_api_surface.py (asserts the reader signatures at 80-81).
- documents/: utils.py extract_google_doc_id :15; adapters/google_docs.py replace_placeholders :33, fetch_document_snapshot :62, apply_document_edits :86, all on integrations.google_workspace.client.get_docs_service, no subject.
- drive/adapters/google_drive.py (147): list_folder_files :54, list_child_folders :62, create_folder :70, create_document_from_template :80, find_document_by_channel_name :90 through infrastructure.drive get_drive_provider(); add_metadata :105, delete_metadata :115, get_metadata :125 on the gateway's get_drive_service; incident_drive_healthcheck :134 (reads report_template_id :137).
- scribe/adapters/google_docs.py (1,415): GoogleDocsIncidentDocument :141 (read_sections :144, write_draft_document :192); gateway get_drive_service :321, :1325; infrastructure.drive.DRIVE_SCOPES :30; folder_id :1347. scribe/ports.py IncidentDocumentStore :19, IncidentReportLinkLookup :38; scribe/providers.py :16, :22; scribe/adapters/slack.py SlackIncidentReportLinkLookup :18 (bookmarks_list for "Incident report").
- Production importers: scribe/providers.py:10-11; scribe/service.py:39, 258; jobs/scheduled_tasks.py:12, 176 (the drive healthcheck); modules/incident information_update.py:8, incident_conversation.py:12, incident_status.py:5 (documents.utils); incident_roles.py:8, 20-21, 63; core.py:11, 185; incident_folder.py:19, 37, 68, 87, 109, 117, 127; incident_helper.py:10, 352; incident_document.py:11, 16, 35.
- Test importers and patch strings: tests/unit/features/incident/documents/test_incident_documents_adapter.py (15-136), test_incident_documents_boundaries.py:3; drive/adapters/test_incident_drive_adapter.py:8-66; scribe/test_incident_scribe_draft_adapter.py:10-17, test_incident_scribe_providers_document_store.py:10, test_incident_scribe_slack_adapter_lookup.py:9-83, test_incident_scribe_conversation_draft.py:14, 117; tests/unit/modules/incident/test_incident_timeline_update.py:12-14; tests/unit/server/test_server_app_import_google_settings_lazy.py:28-29; tests/integration/legacy_surface/conftest.py:46-49, 176-179.
- pyproject.toml import-linter ignores :303-305 (drive adapter -> infrastructure.drive, .factory, .models) and :306 (scribe google_docs -> infrastructure.drive).
- Gateway: integrations/google_workspace/client.py factories each take scopes and delegated_user_email=None (:116-162); _build_service :187-189 falls back to tenant.delegated_user_email. No incident adapter passes a subject today; the tenant default still delegates every call until TASK-181.
- Slack writes exist only in legacy modules/incident (core.py bookmarks_add/setPurpose/invite/postMessage/canvas; incident_roles.py:24-54; incident_helper.py:501 archive; incident_status.py:70; information_update.py:317-323). No feature code writes to a conversation; no writability check exists in code (ADR incident-management.md:48, :103).
- [incident_core] folder_id and report_template_id: common/settings.py:49-50, base.toml:200-201 (env_only, ""). Readers: scribe google_docs :1347, incident_folder.py:37, 68, incident_helper.py:352, drive adapter :137, incident_document.py:35.
- Drive folders as products (legacy): core.py:96-106 _find_product_folder lists the child folders of folder_id by product name to file the report; incident_folder.py folder-metadata modals (incident_helper.py:150-154), on_call.py:23 reads the Opsgenie schedule from folder appProperties; incident_roles.py:20-21 writes ic_id/ol_id appProperties on the document; find_document_by_channel_name reads them.

## Steps
### 12a TASK-145.6.1 (mechanical move, no new types, no behaviour change)
1. Create features/incident/core/adapters/google_docs.py holding, verbatim, the bodies of documents/adapters/google_docs.py, documents/utils.py, drive/adapters/google_drive.py (folders, metadata, healthcheck: the incident Drive calls TASK-120 expects here) and scribe/adapters/google_docs.py. One module, sections in that order; private names kept. If reviewers prefer, the 1,415-line section writer becomes core/adapters/google_docs_sections.py imported only by google_docs.py (still one adapter; OQ3).
2. Repoint every production and test importer and mock.patch string listed above (migration.md rule 5), including jobs/scheduled_tasks.py and modules/incident/*.
3. Delete features/incident/documents/, features/incident/drive/, scribe/adapters/google_docs.py; the umbrella layers contract drops documents and drive; pyproject ignores :303-306 renamed to the single core adapter module (count does not grow).
4. Tests move: documents/ and drive/ adapter tests and the scribe draft adapter test to tests/unit/features/incident/core/test_incident_core_google_docs_*.py, patch strings updated only.
### 12b TASK-145.6.2 (IncidentReport)
5. core/api.py: IncidentReport Protocol, every method taking the ReportReference from the record (never a channel name): create_from_template(title, *, placement) -> OperationResult[ReportReference]; replace_placeholders(ref, values); set_status_text(ref, status); append_timeline_entry(ref, entry); read_sections(ref); write_draft_copy(ref, sections, fields, links) -> OperationResult[ReportReference]; link(ref). get_incident_report() provider beside the reader's.
6. core/adapters/google_docs.py: GoogleDocsIncidentReport implements it over the moved functions; Drive calls move from infrastructure.drive to the gateway's get_drive_service (paged list, create, copy, find by name), so ignores :303-306 are deleted (TASK-120 AC #2 lands here). No adapter passes delegated_user_email or builds credentials (AC #7). folder_id and report_template_id read at call time from [incident_core].
7. Placement (OQ1): create_from_template(placement=<legacy product name or None>) files the report in the matching child folder of folder_id, else folder_id; the adapter owns this as report placement, not a catalogue (2026-11-04 note). modules/incident/core.py _find_product_folder is replaced by it.
8. scribe: IncidentDocumentStore and get_incident_document_store go; scribe/service.py takes IncidentReport from core.api. Legacy incident_document.py, incident_status.py, information_update.py call the adapter's functions as today (rule 5); legacy folder-metadata admin, on_call.py and incident_roles.py metadata keep calling the moved module functions, which are not on the Protocol (OQ2).
9. AC #6: subdomains using the report (scribe now; response at 145.7) state folder_id and report_template_id as required when they register; boot fails naming the key when empty (plugins.md). Production has both set, so no boot change there.
10. core/adapters/in_memory.py: InMemoryIncidentReport.
### 12c TASK-145.6.3 (IncidentConversation and the reader)
11. core/api.py: IncidentConversation Protocol on ConversationReference: post(ref, blocks/text), set_purpose(ref, text), add_bookmark(ref, title, link), invite(ref, people), archive(ref), is_writable(ref) -> OperationResult[bool]; conversation_is_writable(conversation, ref) helper next to find_incident_for_conversation (ADR :48). get_incident_conversation() provider.
12. core/adapters/slack.py: SlackIncidentConversation beside the transcript reader, same client factory and classify_slack_error; is_writable is conversations.info is_archived (and not_in_channel -> False). In-memory fake in in_memory.py. No legacy caller is repointed here (writes are rebuilt in 145.7/145.8/145.10, its consumers).
13. IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe/service.py (:272, :558, :934, :1023) and comms/service.py (:76, :193, :375) resolve the record with find_incident_for_conversation and pass incident.conversation; scribe uses incident.report for the link. IncidentReportLinkLookup, scribe/adapters/slack.py and its provider are deleted; legacy_surface conftest patches updated; test_incident_core_api_surface.py follows the new signatures.

## Domain-model evolution gate
No stored entity changes; the ports consume ConversationReference and ReportReference already in core/domain.py (:181, :186) and on the record (:259-260). Scenario walk:
| Scenario | Conversations | Reports | Holds because |
| --- | --- | --- | --- |
| Single-team outage (today) | 1 | 1 | every call takes the record's reference |
| Legacy item (no record_version) | 1 from the bridge | 0 or 1 | report None -> scribe answers "no report" as today, never a channel-bookmark guess |
| Archived channel, record update | 1 archived | 1 | is_writable False blocks only conversation writes (ADR :48) |
| Coordinated incident, linked workstreams (TASK-165.5) | many, one per linked incident | one per incident | ports are per reference, not per incident; no "the incident's channel" lookup |
| Security incident, restricted | 1 private | 1 restricted | the adapter acts as the bot (rule 5); visibility unchanged by the port |
| Second suite (Teams, M365) | per system | per system | one adapter per interface, selected by the reference's system |
| No report system (adopter without Google) | 1 | 0 | report provider not required unless a subdomain registers needing it (AC #6) |
Rejected: a channel-name report lookup (find_document_by_channel_name) on the Protocol (one-to-one assumption, breaks linked incidents); a ProductCatalog over Drive folders (ADR 2026-11-04). Placement by legacy product name stays an adapter detail and is removed when TASK-165.1 gives products catalogue ids.

## AC traceability
| AC | Layer/steps | Tests |
| --- | --- | --- |
| 1 (Protocols, one adapter each, fakes; ProductCatalog dropped, see comment) | 12b 5-6,10; 12c 11-12 | test_incident_core_report_*.py, test_incident_core_conversation_*.py |
| 2 (three sources deleted; one Google Docs adapter) | 12a 1-3 | rg -l "google_docs" features/incident shows core only; boundaries test |
| 3 (reader takes a reference; lookup gone) | 12c 13 | test_incident_core_transcript_reader_*.py; rg IncidentReportLinkLookup app empty |
| 4 (no visible change) | all | legacy_surface suite, scribe and comms suites |
| 5 gates | all | ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership, pytest |
| 6 (ids from [incident_core], required on register) | 12b 6, 9 | test_incident_core_report_settings_required.py (empty key -> plugin_boot_failed naming it) |
| 7 (no subject, no credentials) | 12b 6 | test_incident_core_report_google_no_delegation.py: factories called with scopes only; no google.oauth2 import in core/adapters |

## Test matrix
Report: create from template (placement found, not found -> root folder, placement None), placeholders, status text, timeline append, read sections, draft copy; HttpError 403/404/5xx -> classified OperationResult; empty folder_id -> config failure; fake parity. Conversation: post, purpose, bookmark, invite (already in channel is success), archive, is_writable (open, archived, not_in_channel), SlackApiError classified. Reader: by reference, started-at, reference of another system -> unsupported. Scribe/comms: command in a non-incident channel -> not-an-incident reply unchanged; incident without report -> unchanged reply.

## Assumptions and doubts
- The move in 12a is verbatim; verified by the moved tests passing with patch strings changed only.
- Replacing infrastructure.drive calls with the gateway (12b) preserves pagination and supportsAllDrives; verify against infrastructure/drive/google.py _list/_collect_files before writing, and pin with tests.
- appProperties stay readable: same service account and OAuth client (TASK-169 D1); 145.6 does not change who the calls run as (the tenant default delegation stays until TASK-181).
- #1821/#1822 overlap on core/api.py, base.toml, README and the api-surface test: resolved by building above 11c.

## Blast radius and rollback
12a: import breakage only, caught at import by the suites; one revert. 12b: report creation, status text, timeline and scribe drafts go through the new adapter: a bug breaks report edits on declare, caught by the moved tests and legacy_surface; one revert. 12c: scribe and comms read transcripts by reference: a bug breaks /incident draft and comms summaries, not declare; one revert. No terraform, IAM, SSM or env-name change: no deploy-checks required.

## Open questions (recommendation first)
- OQ1 placement: keep filing the report in the product-named child folder as an adapter placement hint (recommended, behaviour-preserving); alternative: always file under folder_id (user-visible change, rejected).
- OQ2 legacy folder admin and on-call metadata functions: move into core/adapters/google_docs.py as plain module functions off the Protocol, deleted with modules/incident (TASK-145.13) and the on-call re-cut (TASK-146) (recommended, lets drive/ go now per TASK-120); alternative: leave drive/ for TASK-120.
- OQ3 the 1,415-line section writer: one module (recommended for 12a, a pure move) with the option to split into google_docs_sections.py in 12b if review asks.
- OQ4 the section writer's "cds staff" labels (scribe google_docs :92-118) match the configured template's headings, not app wording: move verbatim; per-template label sets belong to TASK-165's per-type document templates (recommended, recorded there); no override loader exists yet (infrastructure/i18n has merge only).
- OQ5 AC #1 rewording and title/description without ProductCatalog (comment proposes; applied on approval).

2026-11-05 approval: split into TASK-145.6.1 (12a), 145.6.2 (12b), 145.6.3 (12c); OQ1-OQ5 approved as recommended (OQ3: one module). ACs renumbered after the AC #1 rewording: old #2-#7 are now #1-#6, the reworded AC #1 is #7.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 re-ground: IncidentReport stays one feature-owned Google Docs adapter; no documents capability until a second suite or consumer exists (decisions/workplace-systems.md rule 2). Under the TASK-147 flag the report becomes the narrative document only (TASK-147.7); with the flag off its behaviour is today's. ProductCatalog over Drive folders is interim: products are a record of truth that belongs in the app's records (DRAFT-2).

2026-10-14 (TASK-145.5 split): conversation_is_writable (the second part of the command check, incident-management.md:44) moved here from TASK-145.5 and is served by IncidentConversation. The 2026-10-09 plan predates the split and the svcs registry; re-plan after TASK-145.5.5 is implemented. Stack K layer 10.

2026-10-15: Stack K layer 11 after the legacy item bridge (TASK-145.5.8) was inserted as layer 6; depends on it because the report and conversation references come from the record, legacy items included.

2026-10-19: Stack K layer 13 after TASK-145.5.5 was split (TASK-145.5.9 and TASK-145.5.10 are layers 7 and 8, the cutover layer 9); re-plan after the cutover is implemented.

- 2026-10-28 (TASK-167 accepted): the scribe labels carry CDS wording (cyber.gc.ca, security@cds-snc.ca, 'CDS Staff'); organisation wording is provisioned message overrides by key over generic app strings (decisions/organisation-content.md). The surface that absorbs or rebuilds each label moves it there (this task for scribe's section writer, 145.11 for the rest of scribe).

2026-11-04 (human approved, coordinated-incidents reconciliation): option C: ProductCatalog is out of this task's scope. Drive folders are never a source of products (incident-management.md 2026-11-04); TASK-165.1 builds the ProductCatalog port with its catalogue adapter (Backstage) once the product-catalog ADR defines a product. Listing the incident Drive folders, if declare still needs it, is report-placement configuration of the IncidentReport adapter, not a catalogue. The Opsgenie schedule read from folder metadata belongs to the on-call capability (TASK-146), not here. Re-check the title, description and ACs at re-plan (after layer 11).

2026-11-05: no longer waits on TASK-169 (TASK-169 ruling, 2026-11-05 (human), D6): the credential model is invisible to its ports; AC added instead. Drive and Docs run as the service account itself after TASK-181 (shared-drive member), same account, so the appProperties it reads stay visible.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T00:25:00Z

---

2026-11-05 re-plan, proposed: AC #1 reworded to 'IncidentConversation and IncidentReport are Protocols in core/api.py with one adapter each in core/adapters/ and in-memory fakes; ProductCatalog is TASK-165.1's (option C, 2026-11-04)'; title becomes 'Add the core resource interfaces IncidentConversation and IncidentReport (absorbing documents/, drive/ and scribe's section writer)'; description drops the ProductCatalog bullet. Applied on approval with the split into TASK-145.6.1-145.6.3.

---

created: 2026-11-05T00:37:00Z

---

2026-11-05 (human): OQ2 approved (legacy folder and metadata functions move into the core adapter off the Protocol, subject to lint-imports and the ADRs). OQ3 approved: the section writer stays one module. Open: OQ1, OQ4 (context given), OQ5 and the ProductCatalog source (TASK-165.1 currently names Backstage as its only adapter; human: the bot must not depend on Backstage, as it must not depend on Slack or Teams).

---

created: 2026-11-05T00:43:00Z

---

2026-11-05 (human): plan approved. Split approved into three layers (prefer fewer PRs where the rules allow; the move stays separate from the new interfaces per CLAUDE.md). OQ1 approved (report placement in the legacy product folder as an adapter hint). OQ4 approved (template labels move verbatim; per-template label sets with TASK-165's per-type document templates). OQ5 applied: title, description and AC #1 (now AC #7 after renumbering) drop ProductCatalog. ProductCatalog's default source is the bot's own product list (TASK-165.1, ADR amended).

---
<!-- COMMENTS:END -->
