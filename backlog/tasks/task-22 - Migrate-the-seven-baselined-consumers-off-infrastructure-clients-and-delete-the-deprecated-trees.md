---
id: TASK-22
title: >-
  Migrate the seven baselined consumers off infrastructure/clients/ and delete
  the deprecated trees
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 21:13'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-19
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - 'https://github.com/cds-snc/sre-bot/issues/1276'
priority: high
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/layers.md (Migration) and decisions/outbound-clients.md. Today three client generations coexist: empty app/clients/ (aborted name), deprecated app/infrastructure/clients/{aws,google_workspace,maxmind}/ (72 files) still imported at runtime by the baselined consumers (infrastructure/storage/service.py:19, infrastructure/directory/factory.py:6, infrastructure/directory/google.py:7, packages/geolocate/service.py, packages/access/sync/providers.py, packages/access/sync/adapters/aws_identity_center.py), and current app/integrations/.

Steps:
1. Run make client-usage-matrix (task-19) to get the authoritative consumer list (the plan counted 7 baselined files).
2. Migrate each consumer to the app/integrations/ equivalent, one consumer (or one vendor) per PR to keep review small.
3. After the last consumer: delete app/infrastructure/clients/ entirely and the empty app/clients/ directory.
4. Empty the corresponding baseline in app/bin/baselines/ as consumers migrate (the freeze check enforces monotonic shrinkage).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 make client-usage-matrix reports zero consumers of infrastructure/clients/
- [ ] #2 app/infrastructure/clients/ and app/clients/ no longer exist; decisions/layers.md check "no directory named clients/ under app/" passes
- [ ] #3 Deprecated-import baseline file is empty
- [ ] #4 All tests pass after each per-consumer PR, not just the last one
- [ ] #5 Across the sprint, legacy test counts under tests/modules/ and tests/integrations/ only decrease: every vendor test touched during a slice is relocated to tests/unit/ or tests/integration/ (never left in or added to the legacy trees)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: no functional change per migrated consumer (existing tests unchanged except import paths)
- [ ] #2 PR series references decisions/layers.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
TASK-22 is an UMBRELLA. It ships as 5 dependency-chained subtasks, one reviewable PR each, run in strict order as one sprint. TASK-22 itself is Done only when all 5 subtasks are Done.

SCOPE BOUNDARY (critical): subtasks wire the 6 production consumers to the integrations/ modules AS THEY EXIST TODAY (including _next.py twins and clients that still return OperationResult). They do NOT rename _next files (that is downstream TASK-23) and do NOT apply the clients-raise/adapters-classify contract or retire the shield/executor tier (that is downstream TASK-25). Chain: TASK-19 -> 22.1 -> 22.2 -> 22.3 -> 22.4 -> 22.5 -> TASK-23 -> TASK-25. TASK-23 and TASK-25 were repointed to depend on 22.5.

SLICE ORDER + AC TRACEABILITY (each slice is behavior-neutral):
1. TASK-22.1 MaxMind/geolocate. Consumer: packages/geolocate/service.py:12. Target: integrations/maxmind (ADD OperationResult client coexisting with legacy tuple geolocate()/healthcheck() kept for api/v1/routes/geolocate.py + jobs/scheduled_tasks.py). Feeds parent AC#1/AC#2. Tests: move tests/integrations/maxmind -> tests/unit/integrations/maxmind.
2. TASK-22.2 AWS DynamoDB/storage. Consumer: infrastructure/storage/service.py:19,262. Target: integrations/aws/dynamodb_next. Preserve DynamoDBStorageService public surface. Feeds parent AC#1. Tests under tests/unit already; add dynamodb_next unit tests.
3. TASK-22.3 AWS IdentityStore/access-sync. Consumers: packages/access/sync/providers.py:3 + adapters/aws_identity_center.py:21 (~9 identitystore.* calls). Target: integrations/aws/identity_store_next (verify method-name mapping). Feeds parent AC#1. Tests: move tests/integrations/aws/test_identity_store_next.py -> tests/unit/integrations/aws.
4. TASK-22.4 Google directory. Consumers: infrastructure/directory/factory.py:6 + google.py:7 (11 directory.* calls, incl. health_check). Target: integrations/google_workspace/google_directory_next (VERIFY/ADD health_check parity). Feeds parent AC#1. Tests: move google_directory_next + google_service_next tests -> tests/unit/integrations/google_workspace.
5. TASK-22.5 Cleanup. Delete infrastructure/clients/ (72 files) + empty app/clients/; delete tests/unit/infrastructure/clients/*; repoint tests/unit/infrastructure/services/test_narrow_slice_providers.py:13; empty TASK-19 baseline if landed; update decisions/layers.md Migration (drop 'infrastructure/clients/ consumers' divergence). Satisfies parent AC#1,#2,#3,#4,#5.

PARENT AC MAP: AC#1 (usage-matrix zero) verified in 22.5; AC#2 (dirs gone + layers.md check) in 22.5; AC#3 (baseline empty) in 22.5 (no-op if TASK-19 not landed, see TASK-19 comment); AC#4 (tests pass per-PR) enforced in every slice DoD; AC#5 (legacy test counts only shrink) enforced per slice via the relocate step.

TEST MATRIX (per slice, behavior-neutral): existing consumer tests must pass with unchanged assertions after import/DI repoint; touched vendor tests relocate from tests/integrations/ or tests/modules/ into tests/unit/ or tests/integration/; new target-module unit tests added where missing (notably dynamodb_next). Run: cd app && uv run pytest tests --ignore=tests/smoke; plus make audit-client-usage-matrix at 22.5.

ASSUMPTIONS / DOUBTS TO VERIFY IN IMPLEMENTATION:
- A1 identity_store_next covers all 9 adapter methods with matching semantics (verify name mapping get_user_id_by_username->get_user_by_username, describe_group->get_group; check create/delete_group_membership signatures). Verify by reading identity_store_next.py before editing the adapter.
- A2 google_directory_next lacks a health_check equivalent (research found none) — 22.4 must add one with parity. Verify by grep in integrations/google_workspace before wiring.
- A3 dynamodb_next module-function shape vs DynamoDBStorageService's injected-client shape requires a small wiring decision (call module functions directly vs a thin shim); keep the shim minimal and behavior-neutral (no new abstraction beyond what removal of the facade requires).
- A4 integrations/maxmind tuple API has 2 legacy consumers (api/v1/routes/geolocate.py, jobs/scheduled_tasks.py) that MUST stay untouched in 22.1; unification is TASK-25.
- A5 TASK-19 baseline files may not exist at sprint time (confirmed absent 2026-07-29); 22.5 handles both cases.

BLAST RADIUS / ROLLBACK: each slice is a single PR touching one vendor subsystem; revert = revert that PR (no cross-slice coupling until 22.5 deletion). 22.5 is the only irreversible-ish step (tree deletion) and is gated on 22.1-22.4 all green + a zero-consumer usage-matrix check. import-linter (TASK-18) and the deprecated-import freeze (TASK-19, if landed) provide net-new-import protection during the sprint.
<!-- SECTION:PLAN:END -->
