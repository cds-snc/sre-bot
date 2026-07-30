---
id: TASK-22.1
title: Migrate geolocate off infrastructure/clients/maxmind onto integrations/maxmind
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-29 21:10'
updated_date: '2026-07-30 19:10'
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
  - app/packages/access/sync/adapters/aws_identity_center.py
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
- [ ] #1 packages/geolocate/service.py has no infrastructure.clients.maxmind import and imports the MaxMind OperationResult client only via a new packages/geolocate/adapters/maxmind.py (per decisions/layers.md 'packages/** may import integrations only inside adapters/'; adapter re-exports from integrations/maxmind)
- [ ] #2 integrations/maxmind exposes an OperationResult-returning geolocate client without changing the existing tuple|str geolocate() / bool healthcheck() used by api/v1/routes/geolocate.py and jobs/scheduled_tasks.py
- [ ] #3 geolocate unit + integration tests pass unchanged in behavior; MaxMind tests relocated from tests/integrations/ to tests/unit/integrations/maxmind/ (legacy tests/integrations/ file count reduced)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: geolocate_ip returns identical OperationResult; PR references decisions/layers.md and decisions/outbound-clients.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-07-30): TASK-19 (freeze-check baseline) is Done, so TASK-22.1's only dependency is satisfied. packages/geolocate/service.py:12 currently does `from infrastructure.clients.maxmind import get_maxmind_client` and calls `.geolocate(ip_address=...)`, already returning OperationResult end-to-end (geolocate_ip's own body needs no change beyond the import). infrastructure/clients/maxmind/client.py holds MaxMindClient (OperationResult-returning geolocate/healthcheck) + GeoLocationData dataclass + a `@cache`d get_maxmind_client() factory reading MaxMindSettings via infrastructure.configuration.integrations.maxmind.get_maxmind_settings (~90 LOC, read in full this session). integrations/maxmind/client.py today only has the legacy tuple|str geolocate()/bool healthcheck() free functions, consumed by 2 untouched legacy call sites: api/v1/routes/geolocate.py (`from integrations import maxmind`) and jobs/scheduled_tasks.py — both stay on the tuple API, per the task's own scope note; TASK-25 unifies them later.

CRITICAL FINDING - LAYERS.MD DEVIATION IN THE TASK'S ORIGINAL AC#1 WORDING: decisions/layers.md's Checks section requires "packages/** may import integrations only inside adapters/". The task's original AC#1 literally asked for packages/geolocate/service.py (not an adapters/ file) to import integrations/maxmind directly - that would be a NEW layers.md violation, not a migration off one. The established precedent packages/access/sync/adapters/aws_identity_center.py (imports infrastructure.clients.aws, soon integrations.aws, only from inside its own adapters/ subpackage) confirms the required shape. Fix applied this session: AC#1 reworded (see task's current ACs) to require a new packages/geolocate/adapters/maxmind.py; service.py imports the client factory from that local adapter, never from integrations directly. import-linter (TASK-18) isn't wired yet so nothing fails CI today either way, but this sprint shouldn't create fresh boundary debt for TASK-18/25 to unwind later.

Existing tests/unit/packages/geolocate/test_service.py monkeypatches the string "packages.geolocate.service.get_maxmind_client" - since service.py will still bind a local name get_maxmind_client (now sourced from the adapter, same name), this monkeypatch target is UNCHANGED; zero edits needed to test_service.py.

STEPS:
1. Port MaxMindClient / GeoLocationData / get_maxmind_client (dataclass + class + cached factory, OperationResult-returning) into integrations/maxmind/client.py verbatim from infrastructure/clients/maxmind/client.py, adding the now-needed imports (dataclasses.dataclass, functools.cache, typing.TYPE_CHECKING, infrastructure.operations.OperationResult/OperationStatus) alongside the existing tuple geolocate()/healthcheck() functions (coexisting; zero changes to those two). Update integrations/maxmind/__init__.py to also export MaxMindClient, GeoLocationData, get_maxmind_client alongside the existing geolocate, healthcheck - mirrors infrastructure/clients/maxmind/__init__.py's export list exactly.
2. Create app/packages/geolocate/adapters/__init__.py (new subpackage, first adapters/ dir for geolocate) and app/packages/geolocate/adapters/maxmind.py: a thin adapter re-exporting get_maxmind_client from integrations.maxmind.client (`from integrations.maxmind.client import get_maxmind_client`, `__all__ = ["get_maxmind_client"]`) - the packages/<feature>/adapters/<provider>.py shape decisions/layers.md mandates, following packages/access/sync/adapters/aws_identity_center.py as precedent.
3. Edit packages/geolocate/service.py: replace `from infrastructure.clients.maxmind import get_maxmind_client` with `from packages.geolocate.adapters.maxmind import get_maxmind_client`. No other line changes - geolocate_ip's body, logging, and OperationResult handling stay untouched.
4. Relocate app/tests/integrations/maxmind/test_maxmind_client.py to app/tests/unit/integrations/maxmind/test_maxmind_client.py (add a new __init__.py alongside it, matching the aws/slack sibling test dirs' convention); no content changes - it still targets integrations.maxmind.client's tuple geolocate()/healthcheck(), which are untouched.
5. Add app/tests/unit/integrations/maxmind/test_operation_client.py: port the MaxMindClient/GeoLocationData test cases from tests/unit/infrastructure/clients/test_maxmind.py, updating only the import line to `from integrations.maxmind.client import GeoLocationData, MaxMindClient`. Leave tests/unit/infrastructure/clients/test_maxmind.py itself untouched - the whole tree it lives in is deleted wholesale in 22.5, not per-slice.
6. Deliberately do NOT add a dedicated adapters/test_maxmind.py test for the one-line re-export - existing test_service.py already exercises the effective get_maxmind_client seam end-to-end via monkeypatch, and a test asserting a straight re-export equals its source would be a trivial, no-real-assertion test (avoided per implementation-discipline).

AC-TO-STEP-TO-TEST TRACEABILITY:
- AC#1 (no infrastructure.clients.maxmind import in service.py; integrations import confined to the new adapters/maxmind.py) -> Steps 2,3 -> verified by review (grep for `infrastructure.clients` under packages/geolocate/** returns nothing; grep for `integrations` under packages/geolocate/** returns only adapters/maxmind.py) plus the full geolocate test suite collecting/passing (proves the import wiring actually works, not just greps clean).
- AC#2 (integrations/maxmind exposes OperationResult client without touching the tuple geolocate()/healthcheck()) -> Step 1 -> test_operation_client.py (Step 5) proves the new client works; existing app/tests/api/v1/test_geolocate.py (untouched) proves the tuple-consumer route is unaffected; the jobs/scheduled_tasks.py MaxMind call site (untouched, no test edits) proves the other legacy consumer is unaffected.
- AC#3 (tests pass unchanged in behavior; MaxMind tests relocated out of tests/integrations/) -> Steps 4,5 -> file move verified (tests/integrations/maxmind/ empty afterward) + relocated/new tests passing; tests/unit/packages/geolocate/test_service.py passing unchanged proves geolocate_ip's OperationResult behavior is unaffected.
- DoD#1 (behavior-neutral; PR cites decisions/layers.md and decisions/outbound-clients.md) -> full suite green (all steps) + PR description citing both records (human step at PR time).

TEST MATRIX: `cd app && uv run pytest tests/unit/packages/geolocate tests/unit/integrations/maxmind tests/api/v1/test_geolocate.py tests/integration/packages/geolocate -v` first (fast, scoped); then the full `cd app && uv run pytest tests --ignore=tests/smoke`; plus `cd app && uv run ruff check .` and `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` before completion.

ASSUMPTIONS / DOUBTS TO VERIFY IN IMPLEMENTATION:
- A1: jobs/scheduled_tasks.py's MaxMind call site (cited in the task description, not yet read this session) is assumed to use the same integrations.maxmind tuple geolocate()/healthcheck() as api/v1/routes/geolocate.py - verify the exact call during implementation to confirm it needs zero changes, per the task's own explicit scope boundary.
- A2: introducing packages/geolocate/adapters/ is a from-scratch, first-of-its-kind directory for this feature. This is a Path B judgment call (decisions/layers.md's "vendor-neutral question or not" litmus test is arguably ambiguous for a single-vendor geolocation lookup) - flagged for human confirmation rather than silently assumed. Recommendation: Path B (feature-owned adapter) is the right fit for this task's already-approved single-PR scope; a Path A promotion to a shared infrastructure/geolocation/ capability would be a bigger, separate architecture call, better suited to a future task if a second geolocation vendor is ever added.
- A3: no import-linter contract exists yet (TASK-18 still To Do) so this boundary choice isn't machine-enforced this sprint - proceeding compliant-by-design anyway rather than deferring correctness to a future gate.

BLAST RADIUS / ROLLBACK: single vendor subsystem (MaxMind); 5 production files touched (integrations/maxmind/client.py and __init__.py, both additive; packages/geolocate/adapters/__init__.py and maxmind.py, both new; packages/geolocate/service.py, one import line); one test file moved, one test file added. Zero terraform/runtime-settings changes. The 2 legacy MaxMind consumers (api route, scheduled job) are never touched, so their behavior is provably unaffected by construction. Revert = a single git revert of the PR.

SIZE GATE: ~90 ported LOC (client.py) + ~10 LOC adapter + 1-line service.py edit + ~80 LOC ported test file + one file move, 5 production files touched, one cohesive vendor subsystem, no terraform/business-logic crossing. Fits comfortably inside the single-PR gate; no decomposition needed (already the smallest slice of the TASK-22 sprint by design).
<!-- SECTION:PLAN:END -->
