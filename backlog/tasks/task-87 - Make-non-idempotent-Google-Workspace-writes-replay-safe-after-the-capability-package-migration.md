---
id: TASK-87
title: >-
  Make non-idempotent Google Workspace writes replay-safe after the
  capability-package migration
status: To Do
assignee: []
created_date: '2026-09-11 13:59'
labels:
  - clients
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/reliability.md
  - app/integrations/google_workspace/client.py
  - >-
    https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
  - 'https://developers.google.com/workspace/drive/api/guides/create-file'
priority: medium
type: enhancement
ordinal: 187000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md says neither SDK checks idempotency before retrying. A write that isn't naturally idempotent must use the vendor's idempotency mechanism or go through a factory variant with retries disabled. This task replaces the archived TASK-25.1.6.15.

WHY DEFERRED (2026-09-11): planning TASK-25.1.6.15 produced eight subtasks spanning the Google client factory, infrastructure/drive, infrastructure/directory, infrastructure/spreadsheets and four feature adapters. The Google write call sites are expected to consolidate once the clients move out of the feature packages into capability packages. Re-scope this task from scratch when that work is underway. Everything below will have moved by then.

CURRENT STATE (verified 2026-09-11):
- Every Google service is built with a construction-time retry default (GOOGLE_API_NUM_RETRIES=3) and a 10 s per-attempt timeout (GOOGLE_API_TIMEOUT_SECONDS). google-api-python-client 2.198.0 retries any HTTP method on 5xx, 429, rate-limit 403 and socket/connection errors, including timeouts. A write that landed on Google's side but timed out on ours is sent again.
- A stopgap sibling under TASK-25.1.6 passes num_retries=0 at the writes that had no retries before construction-time retry landed: Calendar insert, Meet create, incident_draft Docs copy and batchUpdate, incident documents apply_document_edits, and Sheets values.append. Those writes are replay-safe but get no backoff on 429/5xx. This task removes that per-call override.
- Not covered by the stopgap because they already retried 3 times per call before TASK-25: Drive create/copy and Directory members.insert.

WRITE CALL SITES AND CANDIDATE FIXES (planning research, 2026-09-11):
- app/packages/incident/scheduling/adapters/google_calendar.py:102 events.insert(sendUpdates="all"). Candidate: a client-supplied deterministic event id (characters a-v and 0-9, 5-1024 long); a replay returns 409 duplicate, so fetch and return the existing event. conferenceData.createRequest.requestId only dedups the conference, not the event. Settle the id source jointly with TASK-86 so there is one per-slot key, not two.
- app/infrastructure/directory/google.py:657 members.insert. No token, but a replay after success returns 409 duplicate, which must be reported as success.
- app/infrastructure/directory/google.py:706 members.delete. A replay after success likely returns 404; verify and decide whether that is success.
- app/infrastructure/drive/google.py:97 files.create (folder). Candidate: files.generateIds, then create with that id; a replay returns 409.
- app/infrastructure/drive/google.py:177 and :197 files.copy. Pre-generated ids aren't supported for Google Workspace files (Docs, Sheets), so these need retries disabled. The files.update at :204 moves the copy's parents; verify whether a replay of removeParents fails.
- app/packages/incident/meet/adapters/google_meet.py:24 spaces.create. No documented idempotency key, so retries disabled.
- app/packages/incident_draft/adapters/google_docs.py:324 files.copy (Workspace template). Retries disabled.
- app/packages/incident_draft/adapters/google_docs.py:259 documents.batchUpdate. insertText, deleteContentRange and named-range requests target indices computed against the pre-call document, so an identical replay corrupts it. Retries disabled.
- app/packages/incident/documents/adapters/google_docs.py:78 apply_document_edits. Generic passthrough whose only caller sends insertText and updateParagraphStyle. Retries disabled.
- app/infrastructure/spreadsheets/google.py:129 values.append. A replay appends duplicate rows; the only consumer is modules/incident/incident_folder.py:283 (incident list). Sheets has no idempotency key, so retries disabled.
- Naturally idempotent, no change expected: incident documents replace_placeholders (google_docs.py:37, replaceAllText only), spreadsheets values.batchUpdate (google.py:104, overwrites a fixed range), and the incident drive adapter's files.update calls (google_drive.py:109 and :119, set appProperties).

DESIGN QUESTIONS TO SETTLE WHEN SCOPING:
- Shape of the retries-disabled handle: a retry-count parameter on the existing get_<x>_service factories, or sibling factories. Keep it inside app/integrations/google_workspace/client.py; a new module in the vendor package fails the vendor-package contract guardrail.
- Which capability package owns each write after the migration, and how much the site list above shrinks.
- Expect a split into subtasks under the single-PR size gate.

NOT IN SCOPE: the Google timeout; retry counts for reads; AWS writes; BatchHttpRequest retry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every Google Workspace write call site is recorded in the task notes as naturally idempotent, protected by a vendor idempotency mechanism, or issued through a handle with retries disabled
- [ ] #2 An SDK replay of the retro calendar event insert cannot create a second event or re-send invitations
- [ ] #3 An SDK replay of a Drive create or copy cannot create a duplicate file or folder
- [ ] #4 A replayed Directory members.insert that returns 409 duplicate is reported as success, not failure
- [ ] #5 No Google call site passes num_retries per call; retries are disabled only through a handle configured at construction
- [ ] #6 Read operations keep the construction-time retry default unchanged
- [ ] #7 Unit tests at each changed adapter's SDK seam cover the replay path: a 409 duplicate after a timed-out first attempt, or retries disabled where no vendor mechanism exists
- [ ] #8 decisions/outbound-clients.md's Migration section no longer lists non-idempotent Google writes on the retrying handle or the per-call num_retries override
- [ ] #9 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->
