---
id: TASK-87.2
title: >-
  Report a replayed Directory members.insert (409 duplicate) as success and
  settle the members.delete replay response
status: To Do
assignee: []
created_date: '2026-09-18 15:43'
updated_date: '2026-09-18 15:44'
labels:
  - clients
  - reliability
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/infrastructure/directory/google.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-87
priority: medium
ordinal: 236000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of TASK-87 (human decision 2026-09-18). Directory members.insert has no idempotency token. It is safe to replay only if the duplicate response is read as success, and today it is not.

TODAY (verified 2026-09-18). GoogleDirectoryProvider.add_group_member (app/infrastructure/directory/google.py:632-683) calls members.insert on the retrying handle (GOOGLE_API_NUM_RETRIES=3). Suppose the first attempt lands but its response is lost, for example on a timeout. The SDK resends it, and Google answers 409 'Member already exists'. classify_google_error (app/integrations/google_workspace/client.py) maps only 429/5xx, 404 and 401/403, and re-raises everything else. So the 409 does not even become a failed OperationResult: it propagates as an unhandled HttpError out of a membership add that actually succeeded. remove_group_member (:685-) has the mirror case: a replayed members.delete after success probably returns 404, which would currently come back as NOT_FOUND.

CONSUMERS. The only production callers are packages/access/request/service.py:395/397, :566/568 and :829/831. The access feature is not enabled yet, so no live traffic is affected. The provider is the contract that feature and future consumers rely on.

DESIGN INPUT FOR THE PLANNER.
- A 409 on insert means only that the membership exists. The success payload must still be a DirectoryMember, so the planner decides between a follow-up members.get and building the member from the request. The role on an existing membership may differ from the one requested; decide whether that is still success.
- Decide whether 409 becomes a mapped family in classify_google_error (vendor-wide, e.g. a CONFLICT-style error_code the adapter turns into success) or is handled only at this call site. A vendor-wide mapping changes every Google adapter's error surface, so check the other callers first.
- members.delete: verify what Google actually returns for a replay after success before choosing. Record the evidence (vendor docs, or a Stubber/HttpMock trace of the documented error body) in notes.
- decisions/workplace-systems.md will move infrastructure/directory's consumers onto a capability package later. This change stays inside the provider, so it moves along with it mechanically.

NOT IN SCOPE: the retries-disabled handle (sibling slice), and Drive and Calendar vendor idempotency (TASK-87's later slice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A members.insert that returns 409 duplicate is reported by add_group_member as success with a DirectoryMember, never as an unhandled exception or a failure
- [ ] #2 The members.delete replay response is verified and recorded in notes, and remove_group_member reports it per that decision
- [ ] #3 Unit tests at the SDK seam cover the replay path: a timed-out first attempt followed by 409 on insert (and the verified delete response), plus a genuine error still surfacing as a failure
- [ ] #4 Whether 409 is mapped in classify_google_error or handled only at the call site is recorded, and every other Google adapter is checked against that choice
- [ ] #5 ruff, mypy and pytest tests --ignore=tests/smoke pass, with output recorded in notes
<!-- AC:END -->
