---
id: TASK-25.1.6.15
title: Stop SDK retries from duplicating non-idempotent Google Workspace writes
status: To Do
assignee: []
created_date: '2026-09-10 14:57'
updated_date: '2026-09-10 17:50'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.14
references:
  - decisions/outbound-clients.md
  - decisions/reliability.md
  - app/integrations/google_workspace/client.py
  - >-
    https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
  - 'https://developers.google.com/workspace/drive/api/guides/create-file'
parent_task_id: TASK-25.1.6
priority: high
ordinal: 166000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md says neither SDK checks idempotency before retrying. A write that isn't naturally idempotent must use the vendor's idempotency mechanism or go through a factory variant with retries disabled. The record's Migration section lists "non-idempotent Google writes (Drive create and copy) issued on the retrying handle" as a tolerated divergence. This task closes it.

CURRENT STATE (verified 2026-09-10): every Google service is built with a construction-time retry default (GOOGLE_API_NUM_RETRIES=3, TASK-25.1.6.13). google-api-python-client 2.198.0 retries any HTTP method on 5xx, 429, rate-limit 403 and socket/connection errors, without checking idempotency. A write that succeeded on Google's side but timed out on ours is sent again.

WRITE CALL SITES (grep-verified 2026-09-10; re-verify when planning):
- packages/incident/scheduling/adapters/google_calendar.py:99, `events().insert(sendUpdates="all", conferenceDataVersion=1)`: a replay creates a second retro event and re-sends invitations to every attendee. Highest user impact.
- infrastructure/drive/google.py:95 `files.create`, :175 and :195 `files.copy`: duplicate folders and files.
- packages/incident_draft/adapters/google_docs.py:324 `files().copy`: duplicate draft documents.
- packages/incident/meet/adapters/google_meet.py:24 `spaces().create`: orphaned Meet spaces.
- `documents().batchUpdate` at packages/incident/documents/adapters/google_docs.py:37 and :78, and at packages/incident_draft/adapters/google_docs.py:259: replay safety depends on the request kinds. A repeated replaceAllText finds nothing left to replace; insert-style requests duplicate content. Each site needs a verdict.
- infrastructure/directory/google.py:657 `members().insert`: a replay after success returns 409 duplicate, which must not surface as a failure.
- The legacy mirror modules (integrations/google_workspace/google_calendar.py, google_drive.py, meet.py) are being deleted by sibling tasks and are out of scope.

VENDOR MECHANISMS (verified 2026-09-10 against Google docs; re-check when planning):
- Calendar `events.insert` accepts a client-supplied event `id` (characters a-v and 0-9, 5-1024 long, unique per calendar). A duplicate id returns 409 `duplicate`. Google notes that collisions are not guaranteed to be detected at creation time.
- Drive `files.generateIds`, then `files.create`/`files.copy` with that id: retries after success return 409 and no duplicate is created. But pre-generated ids aren't supported for Google Workspace files (Docs, Sheets) other than folders and drive-sdk files, so copying a Google Doc template can't use this.
- Meet `spaces.create` has no documented idempotency key.

WHY IT MATTERS: incident flows run from Slack interactions and jobs that are already at-least-once (decisions/reliability.md). SDK replays of writes add duplicates people can see: double retro invitations and duplicate documents or folders.

EXPECTED SHAPE: the work spans the Google client factory, infrastructure/drive, infrastructure/directory and several packages/incident adapters, so it is expected to be split into subtasks during planning under the single-PR size gate.

NOT IN SCOPE: the Google timeout (TASK-25.1.6.14); retry counts for reads; AWS writes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every Google Workspace write call site in app/packages and app/infrastructure is recorded in the task notes as naturally idempotent, protected by a vendor idempotency mechanism, or issued through a handle with retries disabled
- [ ] #2 An SDK replay of the retro calendar event insert cannot create a second event or re-send invitations
- [ ] #3 An SDK replay of a Drive create or copy cannot create a duplicate file or folder
- [ ] #4 A replayed Directory members.insert that returns 409 duplicate is reported as success, not failure
- [ ] #5 Read operations keep the construction-time retry default unchanged
- [ ] #6 Unit tests at each changed adapter's SDK seam cover the replay path: a 409 duplicate after a timed-out first attempt, or retries disabled where no vendor mechanism exists
- [ ] #7 decisions/outbound-clients.md's Migration section no longer lists non-idempotent Google writes issued on the retrying handle
- [ ] #8 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-10 17:50
---
COORDINATION FOR PLANNING (2026-09-10, from TASK-25.1.6.11 planning). Two new tasks touch your retro events.insert write site in packages/incident/scheduling/adapters/google_calendar.py:
- TASK-86 (bug, High): modules/incident/schedule_retro.py passes description, reminders and a timestamp-based conferenceData.createRequest.requestId as **event_config. insert_event silently drops all of them and uses its own random requestId. Choosing the requestId source is shared between TASK-86 and this task's replay-safety design, so plan on top of TASK-86's outcome or settle it jointly.
- TASK-25.1.6.11.3 moves generate_unique_id (today's requestId source) verbatim from integrations/utils/api.py into that adapter and removes the unused body_kwargs parameter. It is a pure move, so rebase onto it.
Also: if you add a retries-disabled factory variant, keep it inside integrations/google_workspace/client.py. A new module there will fail TASK-25.1.6.11.2's vendor-package contract guardrail by design.
---
<!-- COMMENTS:END -->
