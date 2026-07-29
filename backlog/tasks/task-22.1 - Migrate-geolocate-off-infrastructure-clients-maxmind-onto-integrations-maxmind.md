---
id: TASK-22.1
title: Migrate geolocate off infrastructure/clients/maxmind onto integrations/maxmind
status: To Do
assignee: []
created_date: '2026-07-29 21:10'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-19
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/packages/geolocate/service.py
  - app/integrations/maxmind/client.py
parent_task_id: TASK-22
priority: high
ordinal: 104000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-22 (parent). Migrate the single MaxMind consumer packages/geolocate/service.py:12 (get_maxmind_client) off the deprecated infrastructure/clients/maxmind tree.

CONFLICT NOTE: integrations/maxmind/client.py already exists but serves two LEGACY consumers (api/v1/routes/geolocate.py:4,14 and jobs/scheduled_tasks.py:11,108) with tuple|str / bool return shapes. Do NOT change those signatures. Instead ADD an OperationResult-returning client (port the working infrastructure/clients/maxmind/client.py MaxMindClient + get_maxmind_client provider) into integrations/maxmind/, coexisting with the legacy tuple functions. Repoint ONLY packages/geolocate/service.py. Final unification of the two MaxMind shapes and the raise/classify contract is downstream TASK-25 — out of scope here.

Behavior-neutral: geolocate_ip keeps returning the same OperationResult.

Test migration (per sprint requirement): move app/tests/integrations/maxmind/test_maxmind_client.py into app/tests/unit/integrations/maxmind/ and add unit coverage for the ported OperationResult client. Legacy tests/integrations/ count must drop by this file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/geolocate/service.py imports the MaxMind OperationResult client from integrations/maxmind (no infrastructure.clients.maxmind import remains in that file)
- [ ] #2 integrations/maxmind exposes an OperationResult-returning geolocate client without changing the existing tuple|str geolocate() / bool healthcheck() used by api/v1/routes/geolocate.py and jobs/scheduled_tasks.py
- [ ] #3 geolocate unit + integration tests pass unchanged in behavior; MaxMind tests relocated from tests/integrations/ to tests/unit/integrations/maxmind/ (legacy tests/integrations/ file count reduced)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: geolocate_ip returns identical OperationResult; PR references decisions/layers.md and decisions/outbound-clients.md
<!-- DOD:END -->
