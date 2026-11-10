---
id: TASK-145.8.7
title: >-
  Incident core ports are async: IncidentReport, IncidentTranscriptReader,
  IncidentStore and StatusUpdateStore
status: To Do
assignee: []
created_date: '2026-11-10T21:00:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.8.1
references:
  - decisions/outbound-clients.md
  - decisions/transport-slack.md
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
ordinal: 521000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L layer L3b, stacked on TASK-145.8.1 (L3) before TASK-145.8.3 (L6a). Applies the async-port rule (decisions/outbound-clients.md, approved 2026-11-10 on TASK-145.7.6 OQ3 R1/R3): a port consumed from async code is async def; an adapter over a blocking SDK offloads inside its own methods with asyncio.to_thread, bounded by the SDK's per-attempt timeout; callers never offload. Mechanical signature change: IncidentReport (Google Docs/Drive adapter offloads), IncidentTranscriptReader (moves to AsyncWebClient, no thread), IncidentStore and StatusUpdateStore (the DynamoDB-backed stores offload their RecordStore calls; RecordStore stays sync, TASK-25), the in-memory fakes, and every caller in comms/ and scribe/ (about 35 call sites in 12 production files; sync Bolt entrypoints keep asyncio.run until TASK-33). Closes the transport-slack.md:73 reader tolerance and the scribe/service.py sync-in-async calls. Split report/reader vs the two stores if the size gate requires it at full planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentReport, IncidentTranscriptReader, IncidentStore and StatusUpdateStore methods are async def in core; their adapters offload blocking SDK calls internally (the reader uses AsyncWebClient) and their fakes are async; no caller wraps a port call in to_thread
- [ ] #2 Every comms/ and scribe/ caller awaits the ports; sync Bolt entrypoints reach them through asyncio.run only; behaviour tests unchanged apart from awaiting
- [ ] #3 transport-slack.md drops the IncidentTranscriptReader tolerance and outbound-clients.md Migration drops the incident ports from its sync-port list
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
