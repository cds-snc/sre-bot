---
id: TASK-25.1.1
title: Migrate Google Calendar + Meet integrations off execute_google_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:32'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/meet.py
parent_task_id: TASK-25.1
priority: high
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-25.1 (smallest, done first to prove the extraction pattern before the larger Drive slice). Migrate integrations/google_workspace/google_calendar.py and meet.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (CalendarResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Calendar/Meet-specific HttpError families beyond what TASK-22.4 established for Directory). Production consumers (grep-confirmed 2026-07-31): modules/incident/schedule_retro.py (Calendar), modules/incident/core.py (Meet - only its Meet-related calls, not its Drive/other calls, which belong to sibling slices). Also delete integrations/google_workspace/gmail.py and gmail_next.py in this slice (zero production consumers, confirmed via grep; gmail_next.py is also named for deletion in TASK-23's plan - coordinate to avoid double-deleting, verify TASK-23's status at implementation time).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/google_calendar.py and meet.py no longer call execute_google_api_call; both route through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 modules/incident/schedule_retro.py (Calendar) and the Meet-related calls in modules/incident/core.py behave identically (existing tests pass, behavior-neutral)
- [ ] #3 gmail.py and gmail_next.py are deleted; classify_google_error gains any Calendar/Meet-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
<!-- AC:END -->
