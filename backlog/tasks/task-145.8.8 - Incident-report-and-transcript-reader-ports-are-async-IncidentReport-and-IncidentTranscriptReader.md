---
id: TASK-145.8.8
title: >-
  Incident report and transcript reader ports are async: IncidentReport and
  IncidentTranscriptReader
status: To Do
assignee: []
created_date: '2026-11-10T21:44:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.8.7
references:
  - decisions/outbound-clients.md
  - decisions/transport-slack.md
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
ordinal: 521500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L row L3c, a side PR from main after TASK-145.8.7 (L3b) merges; split from TASK-145.8.7 at its full planning (size gate, human 2026-11-10). Applies the async-port rule (decisions/outbound-clients.md) to the two remaining incident ports: IncidentReport (GoogleDocsIncidentReport offloads its googleapiclient calls inside its own methods with asyncio.to_thread; link stays sync, it is pure) and IncidentTranscriptReader (SlackIncidentTranscriptReader moves to the async Slack client from get_async_slack_web_client, no thread). The in-memory report fake and the test-local fake readers become async; callers in scribe/service.py (draft and summarize, the _resolve_*_window_start helpers) and comms/service/draft.py (_read_window) await them. The comms start/save chain is already async after TASK-145.8.7, so no Bolt entrypoint changes here. Closes the transport-slack.md IncidentTranscriptReader tolerance and the outbound-clients.md Migration entry for these two ports.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentReport (create_from_template, list_placements, replace_placeholders, read_sections, write_draft_copy) and IncidentTranscriptReader (conversation_started_at, read_transcript) are async def in core; link stays sync; GoogleDocsIncidentReport offloads its blocking calls with asyncio.to_thread inside its methods; SlackIncidentTranscriptReader uses AsyncWebClient; InMemoryIncidentReport is async; no caller wraps a port call in to_thread
- [ ] #2 scribe/service.py and comms/service/draft.py await the two ports; behaviour tests unchanged apart from awaiting and async fakes
- [ ] #3 transport-slack.md drops the IncidentTranscriptReader tolerance; outbound-clients.md Migration drops IncidentReport and IncidentTranscriptReader from its sync-port list
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
