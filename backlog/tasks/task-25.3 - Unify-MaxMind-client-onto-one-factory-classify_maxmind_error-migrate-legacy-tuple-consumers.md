---
id: TASK-25.3
title: >-
  Unify MaxMind client onto one factory + classify_maxmind_error; migrate legacy
  tuple consumers
status: To Do
assignee: []
created_date: '2026-08-05 16:13'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.5
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/maxmind/client.py
  - app/api/v1/routes/geolocate.py
  - app/jobs/scheduled_tasks.py
parent_task_id: TASK-25
priority: high
ordinal: 122000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/maxmind exports exactly one client construction path + classify_maxmind_error(exc) -> (OperationStatus, error_code, retry_after) mapping AddressNotFoundError/ValueError/GeoIP2Error; the legacy module-level geolocate(ip)->tuple|str and healthcheck()->bool functions are deleted
- [ ] #2 api/v1/routes/geolocate.py and jobs/scheduled_tasks.py (the two legacy tuple/bool consumers) are migrated to call the classify boundary and consume OperationResult, not tuple|str/bool
- [ ] #3 packages/geolocate's existing OperationResult-based path (adapters/maxmind.py, service.py) is unchanged/behavior-neutral
- [ ] #4 classify_maxmind_error has unit test coverage: each mapped exception family -> expected status/error_code/retry_after; one unmapped exception propagates
<!-- AC:END -->
