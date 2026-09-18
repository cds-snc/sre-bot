---
id: TASK-87.3
title: >-
  Use Google's own idempotency mechanisms for Calendar event insert and Drive
  create and copy once those writes reach their capability-package adapters
status: To Do
assignee: []
created_date: '2026-09-18 15:43'
labels:
  - clients
  - reliability
dependencies:
  - TASK-87.1
references:
  - decisions/outbound-clients.md
  - decisions/workplace-systems.md
  - decisions/capability-packages.md
  - app/infrastructure/drive/google.py
parent_task_id: TASK-87
priority: low
ordinal: 237000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Last slice of TASK-87 (human decision 2026-09-18). It is deferred by design: its call sites are expected to move when decisions/workplace-systems.md takes the Drive, Calendar and Directory writes out of infrastructure/ and feature adapters and puts them into capability packages or feature adapters. Re-ground every file and line below when this is scheduled. Do not start before the owning capability package or adapter exists.

REMAINING AFTER THE SIBLING SLICES:
- Calendar events.insert (currently app/packages/incident/scheduling/adapters/google_calendar.py). The sibling slice puts it on the retries-disabled handle. Target: a deterministic, client-supplied event id (characters a-v and 0-9, 5-1024 long), so a replay returns 409 and the existing event is fetched and returned. That also restores backoff on 429/5xx. Settle the id source together with TASK-86, so there is one key per slot, not two. conferenceData.createRequest.requestId only dedups the conference.
- Drive files.create for folders (currently app/infrastructure/drive/google.py:97, on the retrying handle). Target: files.generateIds, then create with that id, so a replay returns 409.
- Drive files.copy (currently app/infrastructure/drive/google.py:177 and :197, on the retrying handle). Pre-generated ids are not supported for Google Workspace files, so these move onto the retries-disabled handle from TASK-87.1. Also verify whether a replay of the follow-up files.update removeParents at :204 fails.

When this lands, decisions/outbound-clients.md's Migration section drops its last Google tolerance (non-idempotent writes on the retrying handle), and TASK-87's AC#1-#3 and #8 can close.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An SDK replay of the Calendar event insert cannot create a second event or re-send invitations, using a client-supplied event id agreed with TASK-86
- [ ] #2 An SDK replay of a Drive folder create cannot create a duplicate folder (generateIds), and Drive copies are issued through a retries-disabled handle
- [ ] #3 Unit tests at each changed adapter's SDK seam cover a 409 duplicate after a timed-out first attempt
- [ ] #4 Every Google Workspace write call site is recorded in notes as naturally idempotent, protected by a vendor mechanism, or retries-disabled, and outbound-clients.md's Migration section no longer lists non-idempotent Google writes
<!-- AC:END -->
