---
id: TASK-38.2
title: >-
  Add the core resource interfaces: IncidentConversation, IncidentReport and
  ProductCatalog with their Google and Slack adapters; IncidentTranscriptReader
  takes the conversation reference
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-09 17:00'
labels:
  - migration
  - phase-5
  - incident
  - superseded
milestone: m-5
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/workplace-systems.md
  - decisions/outbound-clients.md
parent_task_id: TASK-38
priority: medium
ordinal: 307000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SUPERSEDED (2026-10-09) by TASK-145.5: same slice, re-cut for the response | comms | postmortem subdomains, the interim store in packages/incident and the five roles. This task is kept as history and is not to be planned or implemented.

Slice 2 of TASK-38 (expand). decisions/incident-management.md: core/ holds the resource interfaces with two or more subdomain consumers, one adapter per system in core/adapters/, selected by the stored reference.

THIS SLICE
- IncidentConversation (core/api.py): post a message, set the purpose, add a bookmark, invite people, archive, report writability. Slack adapter in core/adapters/slack.py over the Slack Web client factory, try/except plus classify_slack_error, OperationResult.
- IncidentReport (core/api.py): create from a template, replace placeholders, set the status text, append a timeline entry, return the link. Google adapter in core/adapters/google_docs.py, absorbing packages/incident/documents (including IncidentDocumentStore and extract_google_doc_id) and packages/incident/drive; both packages are deleted and every importer, including modules/incident, is repointed (migration.md rule 5: an import-path change in a frozen module).
- ProductCatalog (core/api.py): list products, read a product's on-call schedule and metadata. Drive-folders adapter during the migration; the end state is app records (expansion draft).
- IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference instead of a str; the resolver in core/ selects the adapter by reference.system; scribe/service.py resolves its incident through find_incident_for_conversation and passes the record's reference. IncidentReportLinkLookup is deleted: scribe reads the report reference from the record.
- Templates and Google resource ids are read inside the adapters, never at import time.

Behaviour-preserving: no command, reply or log event visible to users changes. The incident umbrella layers contract shrinks its first layer accordingly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 core/api.py exposes IncidentConversation, IncidentReport and ProductCatalog; each has one adapter per system in core/adapters/ returning OperationResult and frozen domain types; no Slack payload, SDK type or Google id format crosses an interface
- [ ] #2 packages/incident/documents and packages/incident/drive no longer exist; modules/incident imports the report operations from features/incident/core/api.py only; IncidentDocumentStore and IncidentReportLinkLookup are gone
- [ ] #3 IncidentTranscriptReader takes a ConversationReference; scribe resolves its incident through find_incident_for_conversation before reading the transcript; a refusal for an unknown conversation renders the existing no-incident reply
- [ ] #4 Human links for the report and the conversation come from the owning adapter; rg finds no docs.google.com, drive.google.com or slack.com URL built outside core/adapters/ in features/incident/
- [ ] #5 No vendor resource configuration or template is read at import time (import the package with no settings and no network)
- [ ] #6 The legacy_surface suite is green with no assertion change; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries only shrank
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 20:51
---
2026-10-02: input for the IncidentReport Google adapter. A production bug fix made the legacy report timeline write revision-guarded (see the TASK-38.5 and TASK-87 comments of this date). When the report interface is defined, an index-based section write should take the snapshot it was computed from and be rejected on a newer revision, as packages/incident/documents/adapters/google_docs.py::apply_document_edits now does with writeControl.requiredRevisionId; a section rendered from the record does not need the read-parse-rewrite round trip at all.
---
<!-- COMMENTS:END -->
