---
id: TASK-25.1.2
title: Migrate Google Docs integration off execute_google_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:32'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_docs.py
parent_task_id: TASK-25.1
priority: high
ordinal: 113000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.1. Migrate integrations/google_workspace/google_docs.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (DocsResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Docs-specific HttpError families beyond what TASK-22.4/25.1.1 established). Production consumers (grep-confirmed 2026-07-31): modules/incident/incident_document.py, modules/incident/incident_status.py, modules/incident/incident_conversation.py, modules/incident/information_update.py (Docs-related calls only in each file; their Drive-related calls belong to the sibling Drive slice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/google_docs.py no longer calls execute_google_api_call; routes through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 The 4 identified consumer files behave identically for their Docs-related calls (existing tests pass, behavior-neutral)
- [ ] #3 classify_google_error gains any Docs-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
<!-- AC:END -->
