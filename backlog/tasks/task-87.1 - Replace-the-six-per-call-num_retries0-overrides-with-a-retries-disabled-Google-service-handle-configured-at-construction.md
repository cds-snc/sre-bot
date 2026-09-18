---
id: TASK-87.1
title: >-
  Replace the six per-call num_retries=0 overrides with a retries-disabled
  Google service handle configured at construction
status: To Do
assignee: []
created_date: '2026-09-18 15:43'
labels:
  - clients
  - reliability
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/integrations/google_workspace/client.py
  - app/packages/aws_platform/adapters/identity_center.py
parent_task_id: TASK-87
priority: medium
ordinal: 235000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-87, split out 2026-09-18 by human decision so decisions/outbound-clients.md can close before the capability-package work. This slice doesn't depend on where the Google write call sites end up under decisions/workplace-systems.md, because it changes only how a handle is built, not who owns it.

TODAY (verified 2026-09-18). Every Google service is built in app/integrations/google_workspace/client.py::_build_service with requestBuilder=_build_request_builder(GOOGLE_API_NUM_RETRIES). _DefaultingRetryHttpRequest.execute lets a call override that default. Six writes that are unsafe to replay override it per call with .execute(num_retries=0):
- app/packages/incident/scheduling/adapters/google_calendar.py:111 (events.insert)
- app/packages/incident/meet/adapters/google_meet.py:26 (spaces.create)
- app/packages/incident_draft/adapters/google_docs.py:261 (documents.batchUpdate)
- app/packages/incident_draft/adapters/google_docs.py:329 (files.copy of a Workspace template)
- app/packages/incident/documents/adapters/google_docs.py:80 (documents.batchUpdate)
- app/infrastructure/spreadsheets/google.py:140 (values.append)
outbound-clients.md tolerates these overrides as a divergence from 'no retry decision repeated at call sites', until a handle configured at construction replaces them.

GOAL. The factories can build a retries-disabled service, and those six sites use it instead of passing num_retries. Reads and replay-safe writes keep the retrying default.

DESIGN INPUT FOR THE PLANNER.
- Precedent: get_aws_client(..., retries=False) and the second client that packages/aws_platform/adapters/identity_center.py builds for non-idempotent writes. The same shape on the get_<x>_service factories (a keyword that sets the request builder's default to 0) keeps the two vendors consistent. The planner confirms this against sibling factories.
- It must stay inside app/integrations/google_workspace/client.py: a new module in the vendor package fails the vendor-package contract guard.
- httplib2.Http is not thread-safe, and each built service already owns a new Http. A second, retries-disabled service per adapter inherits that rule; neither service may be cached and shared across threads.
- Whether _DefaultingRetryHttpRequest still needs to accept a per-call override once no production caller passes one. Removing it would make AC#2 enforced by construction rather than by grep.

NOT IN SCOPE: Drive files.create/files.copy in infrastructure/drive and Directory members.insert/delete, which stay on the retrying handle. Vendor idempotency mechanisms are TASK-87's later slice, and the Directory 409 handling is its sibling slice. Retry counts for reads, the Google timeout, and BatchHttpRequest are also out of scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each get_<x>_service factory in integrations/google_workspace/client.py can build a service whose requests default to zero SDK retries, chosen at construction; the default build keeps GOOGLE_API_NUM_RETRIES
- [ ] #2 The six listed writes are issued through a retries-disabled service, and no production call site passes num_retries per call (grep returns zero hits outside integrations/google_workspace/client.py)
- [ ] #3 Factory tests assert the retry default of both the retrying and the retries-disabled build, and that each build gets its own authorized Http with the configured timeout
- [ ] #4 Each changed adapter's tests assert the write goes through the retries-disabled service, and reads in the same adapter still use the retrying service
- [ ] #5 decisions/outbound-clients.md's Migration section no longer tolerates the per-call num_retries=0 override, with a dated Changes line
- [ ] #6 ruff, mypy, pytest tests --ignore=tests/smoke, make check-sdk-typing and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
