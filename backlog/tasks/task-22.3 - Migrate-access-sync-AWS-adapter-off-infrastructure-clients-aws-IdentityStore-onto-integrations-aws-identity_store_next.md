---
id: TASK-22.3
title: >-
  Migrate access-sync AWS adapter off infrastructure/clients/aws IdentityStore
  onto integrations/aws/identity_store_next
status: To Do
assignee: []
created_date: '2026-07-29 21:11'
updated_date: '2026-08-04 19:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/packages/access/sync/providers.py
  - app/packages/access/sync/adapters/aws_identity_center.py
parent_task_id: TASK-22
priority: high
ordinal: 106000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-22 (parent). Repoint the access-sync AWS consumers off the deprecated AWSClients facade onto integrations/aws/identity_store_next.

Call sites: packages/access/sync/providers.py:3 (get_aws_clients, injected into AwsIdentityCenterAdapter at line ~37) and packages/access/sync/adapters/aws_identity_center.py:21 (AWSClients type). The adapter calls self._aws.identitystore.<method> at ~9 sites: list_users, list_groups, describe_group, get_user_id_by_username, create_user, delete_user, get_group_membership_id, create_group_membership, delete_group_membership. identity_store_next.py exposes matching MODULE-LEVEL functions returning OperationResult (verify each method name maps: e.g. get_user_id_by_username -> get_user_by_username; describe_group -> get_group). Adjust the adapter constructor/DI so it no longer receives an AWSClients facade. Preserve every OperationResult outcome and error_code normalization (e.g. ResourceNotFoundException -> NOT_FOUND) exactly. Wire to identity_store_next as-is (no _next rename = TASK-23; no raise/classify = TASK-25).

Test migration: relocate app/tests/integrations/aws/test_identity_store_next.py to app/tests/unit/integrations/aws/; keep packages/access/sync adapter tests in tests/unit and tests/integration as already located, updating any mock target paths. Legacy tests/integrations/ count must drop.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/access/sync/providers.py and adapters/aws_identity_center.py no longer import infrastructure.clients.aws; the Path B adapter calls a typed boto3 identitystore client from get_aws_client("identitystore") directly and classifies via classify_aws_error - no AWSClients facade, no identity_store_next dependency, no wrapper class
- [ ] #2 All access-sync adapter unit + integration tests pass behavior-neutral (same OperationResult status/error_code per method, including ResourceNotFoundException -> NOT_FOUND normalization), verified against the method-name mapping (get_user_id_by_username, describe_group, create/delete_group_membership, etc.)
- [ ] #3 classify_aws_error (from TASK-22.2) is reused and extended with any identitystore-specific families, with coverage under tests/unit/integrations/aws/; identity_store_next is left untouched for TASK-23 to delete; any touched vendor test lands under tests/unit or tests/integration (legacy tests/integrations/ count does not grow)
- [ ] #4 moto-backed integration conformance test(s) under app/tests/integration/ exercise the identitystore consumer's create_user/delete_user/get_user_id/describe_user/list_users/create_group_membership/delete_group_membership/list_group_memberships operations against real identitystore semantics via moto.mock_aws() (mirroring tests/integration/infrastructure/idempotency/conftest.py's fixture pattern), additive alongside existing MagicMock-based unit tests -- not a replacement
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: identity-store sync OperationResult outcomes identical (incl. NOT_FOUND normalization); PR references decisions/layers.md, decisions/outbound-clients.md, and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEQUENCED (2026-07-31, decisions/sdk-typing.md): migrates the access-sync AWS adapter DIRECTLY onto the target shape (typed boto3 identitystore client + classify) reusing the get_aws_client + classify_aws_error primitive established in TASK-22.2, instead of onto identity_store_next. Absorbs the IdentityStore portions of the old TASK-23 (rename) and TASK-25 (raise/classify) so the adapter is touched ONCE.

GROUNDING (re-verify at implementation): packages/access/sync/providers.py:3 imports get_aws_clients and injects AWSClients into AwsIdentityCenterAdapter (~line 37); adapters/aws_identity_center.py:21 types the field as AWSClients and calls self._aws.identitystore.<method> at ~9 sites: list_users, list_groups, describe_group, get_user_id_by_username, create_user, delete_user, get_group_membership_id, create_group_membership, delete_group_membership. This is a Path B feature adapter (packages/<feature>/adapters/) - per decisions/layers.md the ONLY feature file allowed to import integrations. VERIFY the boto3 method-name mapping before editing (e.g. get_user_id_by_username -> identitystore get_user_id / list_users filter; describe_group -> get_group / describe_group; create/delete_group_membership signatures) - the facade wrapper method names differ from raw boto3.

TARGET SHAPE: the adapter constructor receives (or resolves via provider) a typed identitystore client from get_aws_client(\"identitystore\") (types-boto3[identitystore], annotate under TYPE_CHECKING); each of the ~9 operations calls the boto3 client directly inside try/except+classify_aws_error, returning OperationResult with OUTCOMES IDENTICAL to today (notably ResourceNotFoundException -> NOT_FOUND normalization the sync flow depends on). Rework packages/access/sync/providers.py so it no longer builds/injects an AWSClients facade.

REUSE, DON'T DUPLICATE: get_aws_client + classify_aws_error already exist from TASK-22.2. Add identitystore-specific expected families to classify_aws_error only if the sync flow observes ones DynamoDB did not (e.g. ConflictException on create membership, ResourceNotFoundException semantics). Do NOT touch shield.py, identity_store_next.py, or the facade tree here (facade deletion = TASK-22.5; dispatcher deletion = TASK-23; shield deletion = TASK-25).

STEPS:
1. Extend integrations/aws classify_aws_error with any identitystore families the adapter's tests assert; add coverage in tests/unit/integrations/aws/.
2. Rework adapters/aws_identity_center.py: replace the AWSClients field with the typed identitystore client from get_aws_client; convert each of the 9 calls to direct-boto3 + try/except+classify, preserving OperationResult outcomes and error_code normalization exactly. Map facade method names -> raw boto3 method names (verified in grounding).
3. Rework packages/access/sync/providers.py: stop importing/constructing get_aws_clients(); resolve the identitystore client via the integrations factory (keep the adapter constructor injectable so tests pass a typed fake).
4. Keep the access-sync adapter unit + integration test assertions unchanged (behavior-neutral); update only mock target paths (patch the boto3 identitystore client, not the facade). Relocate any touched tests/integrations/aws file into tests/unit or tests/integration.

AC-TO-STEP: AC#1 -> Steps 2-3 (grep infrastructure.clients returns nothing; adapter holds typed client + classify). AC#2 -> Step 4 (adapter tests green, NOT_FOUND normalization + per-method status/error_code preserved). AC#3 -> Step 1 + Step 4 (classify reuse/coverage; identity_store_next untouched; test locations). DoD#1 -> full suite + ruff/mypy + PR citing the three records.

TEST MATRIX: happy (each of 9 ops returns the same OperationResult as the facade path); NOT_FOUND (ResourceNotFoundException -> NOT_FOUND on get_user_id_by_username/describe_group); create/delete membership idempotency edges preserved; classify (identitystore families -> expected status/error_code/retry_after; unmapped propagates). Commands: cd app && uv run pytest tests/unit/packages/access/sync tests/integration -k access -v; then tests --ignore=tests/smoke; then ruff check . and mypy (typed identitystore client resolves).

BLAST RADIUS / ROLLBACK: contained to the access-sync adapter + provider wiring + a classify extension; the sync feature's Protocol and other consumers are untouched. Single git revert restores the facade-backed adapter. Ordering: requires TASK-22.2 (get_aws_client/classify_aws_error primitive); independent of 22.4.

SIZE GATE: one adapter file + one provider file + classify extension + tests. Single vendor surface, one reviewable PR.

DOUBTS (verify at impl): (a) exact facade->boto3 method-name/signature mapping for the 9 calls (read integrations/aws/identity_store.py or the facade's IdentityStoreClient to see today's wrapping); (b) whether default_identity_store_id (INSTANCE_ID) currently supplied by the facade must now be threaded through the adapter (it must - pass via settings/provider, not re-read ad hoc); (c) whether identity_store_next has any OTHER consumer (grep) - if zero it is deleted in TASK-23; if some, TASK-23/25 converge them.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-31 17:05
---
RESEQUENCED per decisions/sdk-typing.md (2026-07-31). Original plan wired the access-sync adapter onto integrations/aws/identity_store_next (dispatcher), deferring rename to TASK-23 and raise/classify to TASK-25 - three touches of the same adapter. New plan migrates the adapter ONCE, directly onto a typed boto3 identitystore client + classify_aws_error, reusing the AWS primitive built in TASK-22.2.

AC CHANGES (human review at task-breakdown checkpoint): AC#1 retargeted from "uses integrations/aws/identity_store_next" to "typed boto3 identitystore client from get_aws_client + classify_aws_error (no facade, no identity_store_next dep)". AC#3 retargeted from "relocate test_identity_store_next.py" to "reuse/extend classify_aws_error coverage; identity_store_next left for TASK-23 deletion; touched tests land under unit/integration". AC#2 (behavior-neutral, NOT_FOUND normalization) unchanged in intent. DoD#1 gains decisions/sdk-typing.md.

Dependency unchanged (TASK-22.2), but the coupling is now explicit: this slice REUSES the get_aws_client/classify_aws_error primitive that TASK-22.2 establishes, rather than a second dispatcher wrapper.
---
<!-- COMMENTS:END -->
