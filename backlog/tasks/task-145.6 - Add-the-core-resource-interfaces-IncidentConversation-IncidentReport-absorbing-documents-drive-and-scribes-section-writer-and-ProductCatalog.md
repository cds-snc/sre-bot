---
id: TASK-145.6
title: >-
  Add the core resource interfaces: IncidentConversation, IncidentReport
  (absorbing documents/, drive/ and scribe's section writer) and ProductCatalog
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
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
