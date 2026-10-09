---
id: TASK-145.6
title: >-
  Add the core resource interfaces: IncidentConversation, IncidentReport
  (absorbing documents/, drive/ and scribe's section writer) and ProductCatalog
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:22'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.5
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 356000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer B2 of TASK-145. decisions/incident-management.md: core/ holds the resource interfaces with two or more subdomain consumers, one adapter per system in core/adapters/, selected by the stored reference. Behaviour-preserving.

THIS SLICE
- IncidentConversation (core/api.py): post a message, set the purpose, add a bookmark, invite people, archive, report writability. Slack adapter in core/adapters/slack.py beside the transcript reader.
- IncidentReport (core/api.py): create from a template, replace placeholders, set the status text, append a timeline entry, read sections, write a draft copy with filled sections, return the link. One Google adapter in core/adapters/google_docs.py absorbing features/incident/documents, features/incident/drive and scribe/adapters/google_docs.py (the section writer), so the umbrella has one Google Docs adapter; the three sources are deleted and every importer, including modules/incident, is repointed (migration.md rule 5).
- ProductCatalog (core/api.py): list products, read a product's metadata and on-call schedule reference. Drive-folders adapter during the migration; app records are an expansion.
- IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe and comms resolve the incident through find_incident_for_conversation and pass the record's reference. IncidentReportLinkLookup is deleted: the report reference comes from the record.
- Templates and Google resource ids are read inside the adapters, never at import time. The umbrella layers contract drops documents and drive.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentConversation, IncidentReport and ProductCatalog are Protocols in core/api.py with one adapter each in core/adapters/ and in-memory fakes
- [ ] #2 features/incident/documents, features/incident/drive and scribe/adapters/google_docs.py are deleted; core/adapters/google_docs.py is the only Google Docs adapter in the umbrella
- [ ] #3 IncidentTranscriptReader takes a ConversationReference; IncidentReportLinkLookup no longer exists
- [ ] #4 No user-visible command, reply or log event changes; the legacy_surface suite and the scribe and comms tests pass
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09); paths assume TASK-145.1 to TASK-145.5 merged. Behaviour-preserving. SIZE GATE: the slice as described exceeds ~400 production lines and mixes three new Protocols with the merge of three adapters; the plan proposes two sub-layers (human decision before implementation): TASK-145.6.1 the report, TASK-145.6.2 the conversation and the catalog.

## Discovered state
- Google Docs and Drive code in the umbrella: documents/adapters/google_docs.py (117: replace_placeholders, fetch_document_snapshot, apply_document_edits; integrations.google_workspace.client), documents/utils.py (extract_google_doc_id), drive/adapters/google_drive.py (148: list_folder_files, list_child_folders, create_folder, create_document_from_template, find_document_by_channel_name, add_metadata, delete_metadata, get_metadata, incident_drive_healthcheck; imports infrastructure.drive and infrastructure.configuration.integrations.google: ignore entries pyproject 299-302), scribe/adapters/google_docs.py (1415: GoogleDocsIncidentDocument.read_sections and write_draft_document, _RequestBuilder; ignore entries 303-304). Legacy consumers: modules/incident/incident_document.py (create_incident_document 27, update_boilerplate_text 44, update_incident_document_status 57, update_timeline_section 84-200) over the documents adapter; modules/incident/incident_folder.py (list_child_folders 40-47, metadata 64-94) and incident_roles.py (add_metadata 20-21, find_document_by_channel_name 63) and incident_helper.py (create_folder 354) over the drive adapter.
- Slack conversation operations today: modules/incident/incident_conversation.py (460: channel creation, archive_channel_action 433, timeline reaction handlers), core.py (bookmarks, invites, canvas 464), incident_status.py:70 and incident_roles.py:13 (channel posts). core/adapters/slack.py (216) already holds SlackIncidentTranscriptReader over the Slack client factory.
- ProductCatalog: products are Drive child folders with metadata (incident_folder.py 40-94); modules/incident/on_call.py reads an Opsgenie schedule from folder metadata.
- IncidentTranscriptReader (core/api.py:85) takes a conversation id string; scribe/service.py and comms resolve the incident and pass the id; scribe/adapters/slack.py SlackIncidentReportLinkLookup finds the report link from the channel's bookmarks and is replaced by the record's report reference.

## Steps (as two sub-layers)
TASK-145.6.1 report (mechanical merge plus one Protocol)
1. core/api.py: IncidentReport Protocol: create_from_template(title, folder, template) -> ReportReference; replace_placeholders; set_status_text; append_timeline_entry; read_sections; write_draft_copy(sections, fields, links); link(reference).
2. core/adapters/google_docs.py: one adapter class implementing it by moving the bodies of documents/adapters/google_docs.py, the document-related drive functions (create_document_from_template, find_document_by_channel_name) and scribe/adapters/google_docs.py (GoogleDocsIncidentDocument becomes the read_sections/write_draft_copy half); documents/utils.extract_google_doc_id becomes a private helper. Delete features/incident/documents and the document functions of drive; scribe/adapters/google_docs.py and scribe's IncidentDocumentStore Protocol go, scribe/service.py takes the IncidentReport from core.api. Ignore entries renamed to the core adapter (count unchanged: 299-304 collapse to the same imports from one module).
3. modules/incident/incident_document.py, incident_roles.py:63 import the core adapter functions (migration.md rule 5); behaviour unchanged.
4. Tests: tests under documents/ and the scribe draft adapter tests move to tests/unit/features/incident/core/test_incident_core_report_*.py; legacy tests unchanged.
TASK-145.6.2 conversation, catalog, reference-taking reader
5. core/api.py: IncidentConversation Protocol (post, set_purpose, bookmark, invite, archive, is_writable) with the Slack adapter in core/adapters/slack.py beside the transcript reader, over the Slack client factory with classify_slack_error; ProductCatalog Protocol (list_products, product(metadata, schedule reference)) with the Drive-folders adapter in core/adapters/google_drive.py (the remaining drive functions: folders and metadata; drive/ deleted).
6. IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe/service.py and comms/service.py resolve the record through the store and pass incident.conversation; IncidentReportLinkLookup and scribe/adapters/slack.py are deleted (the report reference comes from the record).
7. modules/incident/incident_folder.py, incident_helper.py:354, incident_roles.py:20 import the core drive adapter; legacy_surface conftest (which patches the lookup) updated.
8. Tests: test_incident_core_conversation_*.py (Stubber-style Slack fakes as the transcript reader tests), test_incident_core_product_catalog_*.py, transcript reader tests take references; scribe and comms service tests pass a reference.

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 (three Protocols, one adapter each, fakes) | 1, 2, 5 | core report, conversation and catalog tests; in-memory fakes in core/adapters/in_memory.py |
| 2 (documents, drive, scribe google_docs deleted; one Google Docs adapter) | 2, 5 | `rg -l google_docs features/incident` shows core only |
| 3 (reader takes a reference; link lookup gone) | 6 | transcript reader tests; `rg IncidentReportLinkLookup app` empty |
| 4 (no visible change) | 3, 7 | legacy_surface suite, scribe and comms suites green |
| 5 | all | gates |

## Test matrix
Report: create from template (Drive copy), placeholders, status text, timeline append, read sections, write draft copy; Google API error -> classified failure. Conversation: each operation; archived channel -> is_writable False; SlackApiError classified. Catalog: list, metadata present/absent, schedule reference parse. Reader: reference-based read, started-at.

## Assumptions and doubts
- The two sub-layers need human approval as tasks (TASK-145.6.1, TASK-145.6.2) before implementation; the parent keeps the ACs.
- The scribe Google Docs adapter (1415 lines) is moved, not rewritten; its tests move with it. If reviewers want it split further, the draft-copy writer can stay a separate module under core/adapters/.
- infrastructure.drive imports move with the code and keep their ignore entries renamed (no growth); the drive capability (TASK-120) later removes them.

## Size
6.1: Protocol +60, adapter merge mostly moves (~1,700 lines moved, ~80 new), importer edits ~20. 6.2: Protocols +60, Slack adapter +150, Drive catalog adapter +60 (moved), reader change +30, importer edits ~30. Each under the gate once split.

## Blast radius and rollback
Behaviour-preserving behind the legacy module; a bad merge of the Docs adapter breaks draft and report edits, caught by the moved tests and the legacy suite. Each sub-layer reverts alone.
<!-- SECTION:PLAN:END -->
