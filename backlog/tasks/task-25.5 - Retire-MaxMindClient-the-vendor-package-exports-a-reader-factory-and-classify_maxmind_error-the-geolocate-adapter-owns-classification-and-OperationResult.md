---
id: TASK-25.5
title: >-
  Retire MaxMindClient: the vendor package exports a reader factory and
  classify_maxmind_error; the geolocate adapter owns classification and
  OperationResult
status: To Do
assignee: []
created_date: '2026-09-18 16:47'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/sdk-typing.md
  - decisions/outbound-clients.md
  - app/integrations/maxmind/client.py
  - app/packages/geolocate/adapters/maxmind.py
  - app/api/v1/routes/geolocate.py
  - app/jobs/scheduled_tasks.py
parent_task_id: TASK-25
priority: high
ordinal: 238000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision). decisions/sdk-typing.md must not claim applies: now while a vendor still ships a client facade. TASK-25.3 (Done) deliberately kept MaxMindClient's OperationResult-returning contract, and that is the divergence this task removes.

TODAY (verified 2026-09-18). app/integrations/maxmind/client.py defines MaxMindClient, a standing wrapper class over geoip2.database.Reader. Its geolocate() and healthcheck() methods open a Reader per call, classify errors internally, and return OperationResult. That breaks:
- sdk-typing.md: its check that no per-vendor client facade exists;
- outbound-clients.md: 'clients raise; adapters classify' and 'clients do not return OperationResult' (the vendor-package guard baselines operation-result:integrations/maxmind/client.py);
- the unexpected-exceptions rule: a bare 'except Exception' turns programmer errors into TRANSIENT_ERROR data instead of letting them propagate.
The package also exports GeoLocationData, a domain dataclass.

PRODUCTION CONSUMERS (re-grep before planning):
- app/packages/geolocate/adapters/maxmind.py, which only re-exports get_maxmind_client and is used by packages/geolocate/service.py:42;
- app/api/v1/routes/geolocate.py:15, a legacy route calling maxmind.get_maxmind_client().geolocate();
- app/jobs/scheduled_tasks.py:125, the healthcheck lambda .healthcheck().is_success.

TARGET. app/integrations/maxmind/ exports a factory for the geoip2 Reader (the SDK handle, which ships its own types) plus classify_maxmind_error, and nothing else. The Reader's lifecycle (open once and reuse, versus per call) is decided and recorded. The try/except + classify + OperationResult translation moves into packages/geolocate's adapter, which becomes a real adapter instead of a re-export, and GeoLocationData moves with it as the domain type. The legacy route and the healthcheck go through that adapter.

OUT OF SCOPE: moving MaxMind settings out of infrastructure/configuration/integrations/maxmind.py (TASK-24 owns every vendor settings move), and MaxMind DB provisioning (TASK-57).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/integrations/maxmind/ contains no class wrapping the SDK and no OperationResult reference; it exports only the Reader factory and classify_maxmind_error, and operation-result:integrations/maxmind/client.py is removed from the vendor-package baseline
- [ ] #2 packages/geolocate's MaxMind adapter calls the Reader directly inside try/except + classify_maxmind_error and returns OperationResult with a domain type; unexpected exceptions propagate instead of becoming TRANSIENT_ERROR
- [ ] #3 The legacy geolocate route and the MaxMind healthcheck reach MaxMind through the adapter, with before/after error-path behaviour recorded per call site
- [ ] #4 The Reader lifecycle (shared vs per call) is decided and recorded, with thread-safety for the async offload stated
- [ ] #5 Classification tests cover each mapped exception family, and one unmapped exception propagates; the adapter has unit tests for the success, not-found and error paths
- [ ] #6 decisions/sdk-typing.md and decisions/outbound-clients.md no longer list MaxMindClient as a tolerated divergence
- [ ] #7 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
