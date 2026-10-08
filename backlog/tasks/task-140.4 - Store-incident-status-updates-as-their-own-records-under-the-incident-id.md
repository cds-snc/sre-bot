---
id: TASK-140.4
title: Store incident status updates as their own records under the incident id
status: Done
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-08 15:49'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 323000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A frozen StatusUpdate record (incident id, sequence, state draft/approved/published, stage, EN and FR fields, author, approver, transcript cutoff, transcript fingerprint, timestamps) and a StatusUpdateStore interface in core/api.py, with an interim adapter directly over integrations.aws (as TASK-140.3; contract (b) forbids the StorageService import of packages/access/sync/job_status_store.py; moves to the storage contract with TASK-108/109) and an in-memory fake. New DynamoDB table sre_bot_incident_status_updates in terraform/dynamodb.tf, PK INCIDENT#<uuid>, SK UPDATE#<sequence zero-padded to 6>, like sre_bot_access_requests, granted to the bot role in terraform/iam.tf. Appends are conditional puts; state changes are conditional writes on the stored state; never read-modify-write or list-append.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Terraform declares sre_bot_incident_status_updates with PK/SK string keys
- [x] #2 The store appends with a conditional put and lists an incident's updates newest first; the latest update is one query
- [x] #3 Records never touch the legacy incidents item or its incident_updates attribute
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #5 The bot role's DynamoDB policy in terraform/iam.tf grants the new table
- [x] #6 A state change (draft to approved to published) is a conditional write that refuses when the stored state has moved on; an SDK retry of the bot's own write is reported as success
- [x] #7 An in-memory StatusUpdateStore in core/adapters/ behaves like the DynamoDB adapter
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Approach
core/ gets the StatusUpdate record, its StatusUpdateStore Protocol, a DynamoDB adapter, and an in-memory fake. The adapter is interim and direct over integrations.aws, the same as TASK-140.3, because contract (b) forbids the StorageService import that job_status_store uses. The Protocol and the key scheme are permanent. The adapter moves onto the storage contract with TASK-108/109.
Keys: PK = INCIDENT#<legacy uuid>, SK = UPDATE#<sequence zero-padded to 6>. Updates are numbered 1, 2, 3 per incident. When two writers claim the same next sequence, the conditional put lets one of them win.

## Steps
1. app/contracts/operations/codes.py: add STATUS_UPDATE_CONFLICT and STATUS_UPDATE_UNREADABLE, alphabetically.
2. app/packages/incident/core/domain.py (+~80):
   - StatusUpdateStage StrEnum, declared in forward order: investigating, identified, monitoring, resolved.
   - StatusUpdateState StrEnum: draft, approved, published, with can_move_to(), which allows only draft->approved and approved->published.
   - StatusUpdateText, frozen, one per language: affected_service, impact, current_action, workaround.
   - StatusUpdate, frozen: incident_id, sequence, state, stage, en, fr, next_update_at, author, transcript_cutoff, transcript_fingerprint, created_at, approver=None, approved_at=None, published_at=None. __post_init__ raises ValueError for a blank incident_id, a sequence below 1, or a naive datetime.
3. app/packages/incident/core/api.py (+~70): add a runtime_checkable StatusUpdateStore Protocol. Every method returns OperationResult and never raises for a store failure.
   - append(update) -> OperationResult[StatusUpdate]: stores a new record at its sequence. When the sequence is taken by a different record, it returns PERMANENT_ERROR + STATUS_UPDATE_CONFLICT.
   - latest(incident_id) -> OperationResult[StatusUpdate | None]: one query. Success(None) means no updates yet.
   - list_for_incident(incident_id) -> OperationResult[Sequence[StatusUpdate]]: newest first, across every page.
   - transition(update, *, expected_state) -> OperationResult[StatusUpdate]: replaces the stored record only while its state is still expected_state. The new state must satisfy expected_state.can_move_to(update.state), otherwise ValueError, before any call. A changed state gives STATUS_UPDATE_CONFLICT.
   Also add a get_status_update_store() lru_cache provider and export the new names in __all__. Update the module docstring.
4. app/packages/incident/core/adapters/status_updates.py (new, ~170): DynamoDbStatusUpdateStore(client).
   - The table name is a module constant: sre_bot_incident_status_updates.
   - append: PutItem with ConditionExpression attribute_not_exists(SK) and ReturnValuesOnConditionCheckFailure=ALL_OLD. If the condition fails and the returned old item equals the new one, the call was an SDK retry of our own write, so it returns success (replay-safe on the standard-retry client). Otherwise it returns CONFLICT.
   - transition: PutItem with ConditionExpression attribute_exists(SK) AND #state = :expected, plus the same ALL_OLD replay check.
   - latest: Query with PK = :pk AND begins_with(SK, :prefix), ScanIndexForward=False, Limit=1.
   - list_for_incident: the query paginator, newest first.
   - Items are typed attributes: S for strings, N for the sequence, M for the en and fr text, ISO-8601 UTC strings for datetimes. An item that fails to deserialize gives PERMANENT_ERROR + STATUS_UPDATE_UNREADABLE and a log entry.
   - SDK errors go through classify_aws_error. A missing table (NOT_FOUND) is remapped to PERMANENT_ERROR. Messages are generic. A warning status_update_store_failed logs the operation, incident_id, status and error_code.
   - build_status_update_store() builds the client in-account (SERVICE_ROLE_MAP dynamodb) with standard retries, at call time.
   - The adapter never names the legacy incidents table or incident_updates.
5. app/packages/incident/core/adapters/in_memory.py (new, ~60): InMemoryStatusUpdateStore. It has the same semantics, including the replay and conflict rules and the newest-first order. The tests of 140.5 and 140.6 inject it.
6. terraform/dynamodb.tf: add aws_dynamodb_table.sre_bot_incident_status_updates, a copy of sre_bot_access_requests (PK and SK as S, 2/2 capacity). terraform/iam.tf: add its ARN to the bot's DynamoDB statement. Without the ARN, every call gets AccessDenied.
7. app/packages/incident/README.md: list the store, the record and the two adapters in the core/ row.

## Tests (TDD, written first), in app/tests/unit/packages/incident/core/
- test_incident_core_status_update_record.py: rejects a blank incident_id, a sequence of 0, and a naive datetime. Covers every pair in the can_move_to matrix and the declared stage order.
- test_incident_core_status_update_store.py uses a real boto3 client and botocore Stubber, which validates every request against the service model:
  - happy: the exact PutItem params for append (key, condition, ALL_OLD), with a round trip of every field through latest. The exact latest Query params (Limit 1, ScanIndexForward False). list_for_incident over two pages chained by ExclusiveStartKey, returned newest first. transition draft->approved stores the approver and the edited text under the state condition.
  - boundary: latest on an incident with no updates gives success(None). An illegal transition (draft->published, published->draft) raises ValueError with no stubbed call.
  - idempotency/conflict: a condition failure whose old item equals the new one gives success. One whose old item differs gives CONFLICT. A transition whose stored state has moved on gives CONFLICT.
  - failure: Throttling -> TRANSIENT with retry_after. ResourceNotFound -> PERMANENT. AccessDenied -> UNAUTHORIZED. EndpointConnectionError -> TRANSIENT. A malformed item -> UNREADABLE. No message carries provider text.
  - AC3: every stubbed request names only sre_bot_incident_status_updates, and no request or item contains incident_updates or the incidents table.
  - builder: get_aws_client("dynamodb") is called only at build time.
- test_incident_core_status_update_fake.py: the in-memory fake meets the same behaviour list (append, replay, conflict, latest, newest first, transition rules).
- test_incident_core_api_surface.py: covers __all__, the Protocol method signatures, a cached provider built on the DynamoDB adapter, and that the fake satisfies the Protocol.

## AC traceability
- AC1: step 6. Verified by terraform fmt -check, and by tf_plan in CI on the PR.
- AC2: steps 3 to 5. Tests: the append and transition condition params, the latest Query with Limit 1, and the two-page list newest first, in both the adapter and the fake.
- AC3: step 4, with its own table and no legacy names. Tests: the AC3 request assertion. Contract checks: lint-imports (e) and (g).
- AC4: the gates.
- AC5: step 6 (iam.tf). Verified by terraform fmt -check and CI tf_plan.
- AC6: steps 2-4. Tests: the transition condition, the conflict, the replay success and the can_move_to matrix.
- AC7: step 5. Test: test_incident_core_status_update_fake.py.
Reverse map: step 1 serves AC2/AC6 (codes), step 2 serves AC2/AC6, step 3 serves AC2/AC6/AC7, step 4 serves AC2/AC3/AC6, step 5 serves AC7, step 6 serves AC1/AC5, step 7 is documentation.

## Size
9 files: 7 production (codes, domain, api, 2 adapters, 2 terraform) plus the README. About 400 production LOC (Python ~380, HCL ~20). Subsystems: packages.incident.core plus terraform, which AC1 requires. This is at the gate's edge, not over it: no mechanical refactor is mixed in, and it is all additive. If it grows, the fake is the piece to defer to 140.5.

## Assumptions and doubts
- Sequences are allocated by the caller: latest().sequence + 1, or 1. A race surfaces as CONFLICT, and 140.5 retries or reports it. Verify in 140.5 planning.
- author and approver are platform user id strings until TASK-83 person references. A follow-up note goes on TASK-83 if it does not cover them.
- workaround is free text. The model and the comms profile decide when it reads "no action needed" (140.5 and 140.6).
- Transition replaces the whole item with a conditional PutItem, not an UpdateItem. It is still a single conditional write, never a read-modify-write of a list.
- The fingerprint format is chosen by 140.5. The store treats it as an opaque string.

## Blast radius and rollback
Purely additive: nothing calls the store until TASK-140.5. One git revert removes the code. The table and the IAM ARN are removed by the next terraform apply. Ordering: tf_apply must create the table and the IAM grant before 140.5 is deployed.

## Decisions (2026-10-07, user)
- Interim boto3 adapter in core/adapters/ behind the Protocol. Rejected: a new contract (b) exemption (the shrink-only rule) and blocking on TASK-108/109.
- SK = UPDATE#<seq:06d>, not UPDATE#<iso ts>#<n>. The conditional put then detects a sequence race. created_at is an attribute.
- State changes are conditional writes in place (draft->approved->published), shipped here so the core interface is complete. Rejected: strict append-only, because "latest approved" would need a filtered query.
- The in-memory fake ships in core/adapters/in_memory.py.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ordering: the sre_bot_incident_status_updates table must be applied in Terraform before TASK-140.5 is deployed.

2026-10-07 (from TASK-140.3 planning): the job_status_store.py pattern reaches StorageService by importing infrastructure.storage, which import-linter contract (b) no-host-imports forbids for packages; the packages.access entries are shrink-only seeded exemptions (pyproject.toml ignore_imports, 'never add one'), so packages.incident cannot copy it without a new exemption. Decide how the StatusUpdateStore obtains storage before implementing (TASK-108 moves the Protocol to contracts/, TASK-109 adds svcs injection; neither has started). For comparison, TASK-140.3 chose an interim direct adapter over integrations.aws in core/adapters/, behind a core/api.py Protocol.

2026-10-07 implementation (TDD: the four test files failed at collection before the code existed, then green).
Files: app/contracts/operations/codes.py (STATUS_UPDATE_CONFLICT, STATUS_UPDATE_UNREADABLE), app/packages/incident/core/domain.py, app/packages/incident/core/api.py, app/packages/incident/core/adapters/status_updates.py (new), app/packages/incident/core/adapters/in_memory.py (new), app/packages/incident/README.md, terraform/dynamodb.tf, terraform/iam.tf; tests: app/tests/unit/packages/incident/core/test_incident_core_status_update_record.py, _store.py, _fake.py (new), test_incident_core_api_surface.py.
Evidence (from app/):
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 57 errors in 20 files (pre-existing), 0 in touched files; uv run mypy packages/incident/core contracts/operations/codes.py -> Success: no issues found in 9 source files
- uv run lint-imports -> Contracts: 10 kept, 0 broken
- terraform fmt -check terraform/dynamodb.tf terraform/iam.tf -> exit 0
- uv run pytest tests/unit/packages/incident/core -> 113 passed
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3807 passed; the 6 (test_webhooks_aws_sns.py x3, infrastructure/directory/test_google.py x3) are the known TASK-90 order leaks and pass in isolation with tests/unit/contracts (187 passed).
Synced: notes on TASK-38.1 (adapter migration to the storage contract), TASK-108, TASK-140.5, TASK-140.6.
Ordering: tf_apply must create sre_bot_incident_status_updates and the IAM grant before TASK-140.5 deploys.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:30
---
2026-10-07: plan approved by the human ("approved as written"); implemented and committed as 56debe1c on task-140.4-status-update-records (pushed). Bottom layer of Stack H (human decision 2026-10-07: 140.4 -> 140.5 -> 140.6 as a stack).
---
<!-- COMMENTS:END -->
