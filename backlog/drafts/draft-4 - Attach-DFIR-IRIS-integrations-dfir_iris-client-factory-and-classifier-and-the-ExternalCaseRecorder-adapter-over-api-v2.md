---
id: DRAFT-4
title: >-
  Attach DFIR-IRIS: integrations/dfir_iris client factory and classifier, and
  the ExternalCaseRecorder adapter over /api/v2
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
labels:
  - incident
  - later-wave
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - 'https://docs.dfir-iris.org/latest/operations/api/'
  - 'https://docs.dfir-iris.org/latest/_static/iris_api_reference_v2.1.0.html'
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2; blocked on this task's own prerequisites). Evidence gathered 2026-10-02 from current documentation (decisions/incident-management.md Context): DFIR-IRIS is LGPL-3.0, self-hosted by docker compose, requires PostgreSQL (12 on v2.4, 18 on v3) plus RabbitMQ and Celery; only /api/v2 survives into v3; API keys are user-bound Bearer tokens (use a service account; renewing revokes the previous key); the UI is English-only.

PREREQUISITES, outside this task: a hosting decision for the IRIS instance itself (it needs PostgreSQL, which is a gated infrastructure change), its network placement (the API is not to be exposed on the Internet; no IP allow-list is documented), and the decision that an English-only responder tool is acceptable for the SRE team.

THIS TASK
- app/integrations/dfir_iris/: build_dfir_iris_client (httpx with explicit timeout and retry policy set once; no retry on non-idempotent POSTs), classify_dfir_iris_error returning the standard tuple, settings (base URL, secret reference). Raw /api/v2 HTTP; the stale v1-shaped dfir-iris-client package is not used.
- features/incident/core/adapters/dfir_iris.py implementing ExternalCaseRecorder: POST /api/v2/cases (case_name, case_description, case_customer, case_soc_id, severity_id, status_id), PUT /api/v2/cases/{id} for updates and close (state_id/status_id), POST /api/v2/cases/{id}/notes and /events for entries. The ExternalCaseReference stores system, instance, the integer case_id and case_uuid; the link comes from the instance base URL pattern recorded at configuration time.
- A key-swap path: a new key is configured and the old one revoked without downtime.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/dfir_iris exports exactly a client factory, classify_dfir_iris_error and settings; factory tests prove explicit timeout and retry and no network I/O at construction
- [ ] #2 The adapter implements ExternalCaseRecorder over /api/v2 only, classifies errors and returns OperationResult; tests cover open, update, add entry, close and each mapped error family
- [ ] #3 An ExternalCaseReference holds system, instance, case_id and case_uuid; the show modal renders the case link from the owning adapter
- [ ] #4 With the instance removed from configuration the no-op recorder takes over without a code change
<!-- AC:END -->
