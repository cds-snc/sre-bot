---
id: TASK-25.2.5.4
title: >-
  Idempotency store: keep the fail-closed claim re-read and make claim
  replay-safe with a claim token
status: Done
assignee:
  - '@me'
created_date: '2026-09-15 20:09'
updated_date: '2026-09-18 14:09'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - app/infrastructure/idempotency/dynamodb.py
  - app/infrastructure/idempotency/lease.py
  - app/tests/unit/infrastructure/idempotency/test_dynamodb_store.py
  - app/tests/integration/infrastructure/idempotency
parent_task_id: TASK-25.2.5
priority: high
ordinal: 217000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.2.5. Independent of .1-.3: the store already uses get_aws_client/classify_aws_error directly (TASK-23.2) and does not use the adapter.

(a) Keep the re-read downgrade (human decision 2026-09-15). In infrastructure/idempotency/dynamodb.py:88-95, a classified SDK failure while re-reading a contended claim returns ClaimResult.IN_PROGRESS. The only production users are leases (infrastructure/idempotency/lease.py, used by the jobs/scheduled_tasks.py singleton jobs and packages/access/sync/platform_lock.py). Returning IN_PROGRESS there fails closed: the run is skipped rather than risking two holders. Put the reason in the claim() docstring and add the unit test, which does not exist today.

(b) Self-replay (human decision 2026-09-15). claim()'s conditional put_item runs on the retrying client. If the first attempt succeeds but its response is lost (timeout or 5xx), the SDK resends. The condition then fails, and the re-read finds our own IN_PROGRESS record, so claim() returns IN_PROGRESS. The lease stays held by nobody until IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS expires. Fix: write a per-call claim_token (uuid4 hex) into the item. On ConditionalCheckFailedException, return NEW if the re-read item is IN_PROGRESS with the same token. The SDK resends the identical request, so the token matches only our own replay. The Protocol, the in-memory store (no SDK replay) and complete/release (replay-safe) are unchanged.

Tests: extend tests/unit/infrastructure/idempotency/test_dynamodb_store.py in its existing MagicMock-client style. The moto conformance suite under tests/integration/infrastructure/idempotency must pass unchanged.

Overlap: TASK-58 later renames this module with identical behaviour; nothing here conflicts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A classified failure of the ConsistentRead after a contended claim still returns IN_PROGRESS; the claim() docstring records the fail-closed lease rationale and a unit test pins the behaviour
- [x] #2 claim() writes a per-call claim_token; when the conditional put fails and the re-read item is IN_PROGRESS with the same token it returns NEW, and with a different or missing token it returns IN_PROGRESS; both cases have unit tests
- [x] #3 The moto conformance suite under tests/integration/infrastructure/idempotency passes unchanged; the IdempotencyStore Protocol, the in-memory store, complete() and release() are unchanged
- [x] #4 Both decisions are recorded in TASK-25.2.5 notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
- [x] #5 decisions/reliability.md's conditional-check-failure branch list gains the self-replay branch (an IN_PROGRESS record bearing the caller's own claim token resolves to NEW), phrased backend-neutrally so it survives the ConditionalWriteStore rename
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RE-VALIDATION 2026-09-17 (siblings .1, .2, .3, .5, .6, .7, .8 have merged)
- Nothing in this task is invalidated. infrastructure/idempotency/dynamodb.py never used
  integrations/aws/dynamodb.py (deleted by .5); it imports only classify_aws_error from
  integrations/aws/client.py:16 and receives its client by injection.
- No guard baseline moves. bin/baselines/aws_platform_seam_consumers.txt (11 entries, all
  modules/* plus jobs/scheduled_tasks.py) names no idempotency file, and neither
  sdk_typing_antipatterns.txt nor vendor_package_contract.txt mentions idempotency.
- AC#4's recording half is already met: both 2026-09-15 decisions are in TASK-25.2.5's notes
  (items 3 and 4, the write-inventory line for dynamodb.py:55, and the blast-radius line
  "the claim item gains one attribute").
- Nothing is started: rg 'claim_token' over app/ -> zero hits; rg 'get_item.*side_effect' over
  tests -> zero hits.

WHAT THIS PRIMITIVE IS FOR TODAY (verified 2026-09-17, and it decides the tone of the docstring)
Leases only. get_idempotency_store() - the dedup singleton - has NO production caller; the only
references are factory.py, __init__.py and tests. TASK-5.2 deleted the last dedup adapter as dead
code with no replacement. Every live claim() arrives through lease.py:19, from
jobs/scheduled_tasks.py:85-88 and packages/access/sync/platform_lock.py:25. The first real dedup
consumer is TASK-37.2 (webhooks ingest, m-4), which codes against the branch list in
decisions/reliability.md - which is why AC#5 puts the new branch there.

WHY THE TOKEN WORKS, AND WHY IT IS THE PORTABLE CHOICE (verified, not recalled)
- botocore/endpoint.py::Endpoint._send_request builds request_dict once and, on retry, calls
  create_request() again over the SAME serialized body - a new signature only. So a replayed
  conditional PutItem carries the identical claim_token AND the identical :now, the condition
  still evaluates false, and the re-read still finds our token. Re-verify after a botocore bump:
  sed -n '/def _send_request/,/def _needs_retry/p' app/.venv/lib/python3.14/site-packages/botocore/endpoint.py
- DynamoDB has no native alternative for this call shape: ClientRequestToken is accepted on
  TransactWriteItems, NOT on plain PutItem. AWS's own guidance for ConditionalCheckFailedException
  under retry is the re-read pattern this code already has. Using the native feature would mean
  rewriting claim() onto TransactWriteItems - a DynamoDB-specific redesign (web review 2026-09-17).
- An opaque per-claim owner token is the portable form: it is the canonical documented Redis
  pattern (SET NX PX plus compare-and-delete), expressible in Postgres (unique insert with an
  owner column) and in Cosmos (etag, or an explicit owner field). It does not strand us on
  DynamoDB, which matters because a backend move is considered plausible.
- It stays OFF the Protocol on purpose. cloud-portability.md rule 4 requires each capability
  Protocol to be faithfully fakeable and free of vendor syntax; the token is a defence against
  botocore's retry, not a property of the coordination contract. A future Redis or Postgres
  adapter answers the same hazard natively. This is also why TASK-102 (ownership-checked
  release/complete), which DOES need the token on the Protocol, is a separate task.
- Not a latent TTL trap: the takeover condition tests the item's own in_progress_expires_at, not
  DynamoDB TTL. DynamoDB TTL deletion is best-effort (documented as possibly up to 48h late), and
  the 'ttl' attribute here is only garbage collection. Behaviour already does not depend on it.

DECISIONS TAKEN 2026-09-17 (human, this planning session)
1. READ-FAILURE POLICY: the fail-closed downgrade STAYS in this PR, and AC#1 is unchanged.
   A web review the same day concluded that fail-OPEN is the better match for a lease whose body
   is idempotent - failing closed skips a whole scheduled period for no correctness gain. But that
   argument rests on decisions/reliability.md's idempotent-body mandate, and the code does not meet
   it: notify_stale_incident_channels (modules/incident/notify_stale_incident_channels.py:14-35)
   posts an interactive nag into EVERY stale incident channel with no dedup, so a duplicate run
   double-posts into live incident channels. Fail-open would also promote the release() hazard from
   latent to active: we only reach the re-read because our put definitively failed, so returning NEW
   hands the caller a lease it does not hold, and run_if_leased releases it in a finally with an
   unconditional delete_item - deleting the real holder's record. Hence: TASK-99 makes the bodies
   duplicate-safe, TASK-100 then flips the policy and rewords AC#1 and its test. The flip is a
   decision already taken; it lands in the right order.
2. ADR: the new branch is recorded in decisions/reliability.md in THIS PR (AC#5).
3. The lease-vs-dedup policy split is recorded as a comment on TASK-58, which builds the facades.
4. Out of scope and filed: TASK-101 (orphan lease when retries are exhausted after the put landed),
   TASK-102 (ownership-checked release/complete), TASK-103 (put_if_not_exists, repointing the
   dangling TASK-27 reference in the parent's notes).

ORDERED STEPS

1. app/infrastructure/idempotency/dynamodb.py - write the token (production, ~4 LOC)
   - Add `import uuid` to the stdlib import block (lines 3-5).
   - In claim(), after `expires_at = now + self.in_progress_ttl_seconds` (line 52), add
     `claim_token = uuid.uuid4().hex`.
   - Add `"claim_token": {"S": claim_token},` to the Item dict (lines 57-63).
   - ConditionExpression, ExpressionAttributeNames and ExpressionAttributeValues are UNCHANGED:
     the token is written, never matched on, by the conditional put.

2. app/infrastructure/idempotency/dynamodb.py - read the token (production, ~4 LOC)
   Between the COMPLETED branch (lines 102-106) and the final `return IN_PROGRESS` (line 108):
       if status == ClaimResult.IN_PROGRESS.name and item.get("claim_token", {}).get("S") == claim_token:
           return ClaimOutcome(result=ClaimResult.NEW)
   COMPLETED stays first, deliberately: our own in-flight claim can never be COMPLETED (only the
   holder completes, and the holder is us, still inside claim()), so no reachable case is reordered.
   A missing attribute yields None, which never equals a hex string.

3. app/infrastructure/idempotency/dynamodb.py - claim() docstring (production, ~14 LOC)
   Extend the existing Behavior list with the fourth outcome, then two short paragraphs:
   - CLAIM TOKEN. Every call stamps a fresh uuid4 hex. botocore resends the identical serialized
     body when a response is lost, so a replayed conditional put fails its own condition and the
     re-read finds our own record; matching the token proves the claim is ours, so the result is
     NEW. Note that this matters for LEASES, not for dedup - a dedup caller treats a replay and a
     real duplicate identically, which is why the Powertools pattern needs no token.
   - FAIL-CLOSED RE-READ. A CLASSIFIED failure of the ConsistentRead returns IN_PROGRESS: we cannot
     tell a real contender from an unreadable store, and we know our own put did not land. An
     UNCLASSIFIED error is NOT downgraded - classify_aws_error re-raises it, because an unknown
     fault is not evidence of contention. State plainly that this downgrade is PROVISIONAL and
     LEASE-SCOPED: decisions/reliability.md treats a Tier-2 lease as a duplication optimization
     with idempotent bodies, which argues for failing open; the bodies are not duplicate-safe yet
     (TASK-99), so skipping one periodic run stays the safer default until TASK-100 flips it.
   Write it as prose a reviewer can check, and name TASK-99/TASK-100 so the provisional status
   cannot quietly become permanent.

4. decisions/reliability.md - the fourth branch (AC#5, ~2 lines)
   Line 18 currently enumerates exactly three conditional-check-failure branches (COMPLETED ->
   recorded outcome; IN_PROGRESS unexpired -> concurrent duplicate, reject/defer; IN_PROGRESS
   expired -> claimant crashed, take over). Add the fourth, phrased backend-neutrally so it
   survives TASK-58's rename and does not read as a DynamoDB detail - e.g. an IN_PROGRESS record
   carrying the caller's own claim token is that caller's own retried write, not a competitor, and
   resolves to NEW. Do not touch line 30's lease doctrine: that is TASK-100's to amend.
   Per governance.md's cascade rule the PR references this record.

5. app/tests/unit/infrastructure/idempotency/test_dynamodb_store.py - tests (~65 test LOC)
   Extend in the existing MagicMock-client style; no new fixtures, no new file. Matrix below.

6. Verification and close-out
   - From app/: `uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`,
     `uv run pytest tests --ignore=tests/smoke`, plus a focused
     `uv run pytest tests/unit/infrastructure/idempotency tests/integration/infrastructure/idempotency -v`
     so the moto conformance evidence for AC#3 is its own line.
     Known-allowed: the order-dependent SNS/google-directory failures recorded on the parent.
   - `backlog task edit 25.2.5.4 --notes` with the actual command output; comment on TASK-25.2.5
     pointing at this task for its AC#4.
   - Files touched: exactly the three above. No terraform, no CI, no baselines, no bin/, no git.

TEST MATRIX (all in tests/unit/infrastructure/idempotency/test_dynamodb_store.py)

| # | Test | Class | Arrange | Asserts | AC |
|---|------|-------|---------|---------|----|
| T1 | test_claim_writes_a_distinct_claim_token_per_call | ClaimNewKey | put_item returns {}; call claim() twice | both Items carry claim_token as a non-empty {"S": ...}; the two values differ | #2 |
| T2 | test_claim_replaying_its_own_conditional_put_returns_new | ClaimConflict | put_item raises ConditionalCheckFailedException; get_item side_effect reads the token back out of put_item.call_args.kwargs["Item"] and returns {"Item": {"status": IN_PROGRESS, "claim_token": <same>}} | result is NEW | #2 |
| T3 | test_claim_on_in_progress_record_with_another_token_returns_in_progress | ClaimConflict | as T2 but the item carries a fixed foreign token | result is IN_PROGRESS | #2 |
| T4 | test_claim_on_in_progress_record_without_a_token_returns_in_progress | ClaimConflict | existing test_claim_on_in_progress_record_returns_in_progress, renamed; item has status only (a record written before this change) | result is IN_PROGRESS | #2 |
| T5 | test_claim_returns_in_progress_when_the_contended_re_read_fails | ClaimConflict | put_item raises ConditionalCheckFailedException; get_item raises ClientError ProvisionedThroughputExceededException (in TRANSIENT_CODES, so classify_aws_error classifies rather than re-raises) | result is IN_PROGRESS; no exception raised | #1 |
| T6 | test_claim_propagates_an_unclassified_re_read_error | ClaimConflict | as T5 but get_item raises ClientError ValidationException | the same ClientError instance propagates | #1 boundary |
| - | existing 7 tests | all | unchanged | unchanged | regression |
| - | tests/integration/.../test_idempotency_store_conformance.py | 9 params x both stores | file untouched | unchanged results | #3 |

T6 is a deliberate addition beyond AC#1's literal text. AC#1 says "a CLASSIFIED failure", and after
TASK-25.2.5.6 the classified/unclassified split is a reviewed boundary in this codebase. Eight lines
pin that the downgrade is scoped, so a later widening of the except clause fails a test instead of
silently swallowing unknown faults. It also protects TASK-100, which must keep that boundary intact.

T2's arrangement: put_item.call_args survives side_effect, and get_item is only reached after
put_item has raised, so reading the token out of call_args inside the get_item side_effect is
deterministic - no hardcoded token, no uuid patching.

The token path is unit-testable only. The conformance suite cannot express it: the token never
leaves claim(), and the in-memory store has no SDK and therefore no replay to simulate. That is the
correct outcome of keeping the token off the Protocol, not a coverage gap to paper over.

AC TRACEABILITY (both directions)
- AC#1 <- step 3 (docstring) and step 2 leaving lines 88-95 untouched; tests T5, T6.
- AC#2 <- steps 1 and 2; tests T1 (per-call), T2 (same token -> NEW), T3 (different -> IN_PROGRESS),
  T4 (missing -> IN_PROGRESS).
- AC#3 <- no edit to protocol.py, in_memory.py, complete() or release(); the conformance file and
  its conftest are untouched; evidence is the focused pytest run in step 6.
- AC#4 <- already recorded in TASK-25.2.5 notes items 3 and 4 (2026-09-15); step 6 runs the gates
  and adds the close-out note plus the parent comment.
- AC#5 <- step 4.
- Every step maps back: 1-2 -> AC#2, 3 -> AC#1, 4 -> AC#5, 5 -> AC#1 and #2, 6 -> AC#3 and #4.

ASSUMPTIONS AND DOUBTS
1. A botocore retry resends the identical serialized body. VERIFIED in botocore/endpoint.py (see
   above), with a re-check command for future bumps.
2. The table tolerates a new non-key attribute. VERIFIED: terraform/dynamodb.tf:86-101 declares
   hash_key idempotency_key and a ttl block only; DynamoDB is schemaless beyond declared keys. No
   terraform change. TASK-5.1's plan recorded the same finding for status/outcome_json.
3. Nothing else reads the raw claim item. VERIFIED by `rg -n 'sre_bot_idempotency'`: the only
   non-test readers are app/bin/unlock-sync-job.sh - which reads .Item.status.S, .Item.claimed_at.N
   and .Item.in_progress_expires_at.N by name at lines 122-124 and then dumps `jq '.Item'` at line
   145, so claim_token simply appears in that dump - and packages/access/sync/job_status_store.py,
   which shares the TABLE but owns disjoint keys and its own record_json attribute. No script change.
4. ProvisionedThroughputExceededException classifies rather than re-raises. VERIFIED:
   integrations/aws/settings.py:83-101 TRANSIENT_CODES. classify_aws_error reads the lru_cached
   get_aws_settings(), and this unit file already depends on those defaults
   (test_claim_mapped_non_conditional_error_raises_runtime_error uses AccessDeniedException).
5. moto honours ConditionExpression on PutItem. Already relied on by the merged conformance suite
   (TestIdempotencyStoreExpiredClaimTakeover); step 6's focused run re-confirms it.
6. The in-memory store needs no token. By construction: no SDK, no network, no replay; one
   threading.Lock makes claim() atomic. The conformance suite asserts Protocol-level outcomes only,
   so it stays green for both implementations.
7. WEAKEST LINK, stated plainly: the fail-closed rationale in the docstring is provisional by
   decision, not by conviction - the 2026-09-17 review favours fail-open for this consumer. It is
   written as provisional and names TASK-99/TASK-100 precisely so it is not mistaken for a settled
   position. If TASK-100 lands first for any reason, step 3's wording is what must be rewritten.

DELIBERATE NON-CHANGES
- The warning at dynamodb.py:90-94 keeps its current fields; the docstring now carries the rationale.
- The token is not surfaced on ClaimOutcome or the Protocol (portability, and AC#3). TASK-102 owns
  the Protocol-level ownership question.
- decisions/reliability.md line 30's lease doctrine is not amended here; TASK-99/TASK-100 own it.
- infrastructure/storage/service.py:138 put_if_not_exists is untouched; TASK-103 owns it.

BLAST RADIUS AND ROLLBACK
- Surface: one production method, claim(), on one class, plus two lines of an ADR. Consumers are the
  two lease call sites (jobs/scheduled_tasks.py:85-88, packages/access/sync/platform_lock.py:25) and
  packages/access/sync/providers.py:27; none changes.
- Wrong in the permissive direction (compares nothing) would let two callers both see NEW. It cannot
  come from a foreign claim - uuid4 - only from a coding error, and T3/T4 are the tests that fail first.
- Wrong in the restrictive direction is today's behaviour: a stuck lease until
  IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS (300s default, or the caller's override) expires. No worse than
  main, and app/bin/unlock-sync-job.sh is the existing operator escape hatch.
- Rollback: one `git revert`. Records written by the reverted code carry an ignored extra attribute
  and expire on their own ttl. No migration, no cleanup, no ordering constraint against any other
  task. Forward and backward deploys interoperate: an old claimant simply never matches a token.

SIZE GATE: PASSES, NO DECOMPOSITION
Production: 1 Python file, ~8 LOC of logic plus ~14 of docstring; 1 ADR, ~2 lines. Tests: 1 file,
~65 LOC. One subsystem. No mechanical refactor mixed in. Single revert restores service. Well inside
the ~400 LOC / ~10 file gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTATION 2026-09-17. Plan followed exactly; three files touched, no others.

CODE (app/infrastructure/idempotency/dynamodb.py)
- step 1: `import uuid`; `claim_token = uuid.uuid4().hex` after expires_at; `"claim_token": {"S": claim_token}` in the Item. ConditionExpression and both ExpressionAttribute maps unchanged - the token is written, never matched on.
- step 2: after the COMPLETED branch, `status == IN_PROGRESS and item.get("claim_token", {}).get("S") == claim_token -> NEW`. COMPLETED stays first; a missing attribute yields None and never equals a hex string.
- step 3: claim() docstring gains the fourth outcome plus the CLAIM TOKEN and FAIL-CLOSED RE-READ paragraphs, naming TASK-99/TASK-100 so the provisional downgrade cannot become permanent by default, and recording why the token stays off the Protocol.
- Lines 88-95 (the fail-closed re-read) are untouched, as AC#1 requires.

ADR (decisions/reliability.md)
- The conditional-check-failure branch list gains a fourth branch: an IN_PROGRESS record bearing the caller's own claim token is that caller's own retried write, not a competitor, and resolves to NEW. Phrased backend-neutrally (DynamoDB attribute / Redis SET NX value / Postgres owner column) so it survives TASK-58's ConditionalWriteStore rename, and it notes the lease-vs-dedup asymmetry. Line 30's lease doctrine untouched (TASK-100 owns it).

TESTS (app/tests/unit/infrastructure/idempotency/test_dynamodb_store.py)
- All six matrix tests T1-T6 authored ahead of the code, in the existing MagicMock style; no new file, no new fixtures. Before the code change T1 and T2 failed on KeyError: 'claim_token' / result mismatch; T3-T6 passed from the start because they pin behaviour that already existed (foreign token, missing token, classified read failure, unclassified propagation) - they are regression pins protecting TASK-100.
- T2 reads the token out of put_item.call_args inside the get_item side_effect, so nothing is hardcoded and no uuid patching is needed.

VERIFICATION (from app/)
- `uv run ruff check .` -> All checks passed!
- `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` -> Found 78 errors in 27 files (checked 354 source files); all pre-existing, none in idempotency (grep -i idempotency over the output: no hits). No new errors.
- `uv run pytest tests/unit/infrastructure/idempotency tests/integration/infrastructure/idempotency -q` -> 82 passed. This is AC#3's evidence: the moto conformance suite passes with its file, its conftest, protocol.py, in_memory.py, complete() and release() all unchanged.
- `uv run pytest tests --ignore=tests/smoke -q` -> 6 failed, 3551 passed. The 6 are the known order-dependent leaks recorded on the parent (3x tests/modules/webhooks/test_webhooks_aws_sns.py, 3x tests/unit/infrastructure/directory/test_google.py); re-running just those two files in isolation gives 111 passed, confirming they are unrelated to this change.

AC#4's recording half was already satisfied by TASK-25.2.5's notes items 3 and 4 (2026-09-15); the gate output above completes it.

Stopping at In Progress for human review. No git operations performed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 20:42
---
PLANNING SESSION 2026-09-17 - decisions and what came out of them.

Scope re-validated against the merged siblings (.1, .2, .3, .5, .6, .7, .8): unaffected. No guard baseline moves. AC#4's recording half was already satisfied by TASK-25.2.5's notes on 2026-09-15.

HUMAN DECISIONS:
1. Fail-closed STAYS here; AC#1 unchanged. A web review on 2026-09-17 favours fail-OPEN for a lease whose body is idempotent, but decisions/reliability.md's idempotent-body mandate is not met in code - notify_stale_incident_channels double-posts an interactive nag into every stale incident channel. Fail-open would also promote the release() hazard from latent to active, since run_if_leased releases in a finally with an unconditional delete_item. Sequenced instead: TASK-99 (make the bodies duplicate-safe) then TASK-100 (flip the policy, reword AC#1 and invert its test).
2. AC#5 ADDED: the self-replay branch is recorded in decisions/reliability.md, whose line 18 currently lists only three conditional-check-failure branches. TASK-37.2 will code against that list.
3. The lease-vs-dedup read-failure policy split is recorded as a comment on TASK-58, which builds the facades and is where a per-use policy belongs.
4. Filed, out of scope: TASK-101 (orphan lease when SDK retries are exhausted after the put landed), TASK-102 (ownership-checked release/complete - needs the token on the Protocol, which AC#3 freezes), TASK-103 (put_if_not_exists; also repoints the dangling TASK-27 reference in the parent's notes).

TWO FINDINGS THAT SHAPED THE PLAN:
- The token must stay OFF the Protocol. cloud-portability.md rule 4 requires each capability Protocol to be vendor-neutral and faithfully fakeable; the token defends against botocore's retry, not against anything in the coordination contract. Verified portable: it is the canonical Redis form, and expressible in Postgres and Cosmos, so it does not strand the design on DynamoDB.
- DynamoDB offers no native alternative for this call shape: ClientRequestToken is accepted on TransactWriteItems, not on plain PutItem. AWS's own guidance under retry is the re-read pattern already in the code.

Verified, not recalled: botocore/endpoint.py::_send_request builds request_dict once and only re-signs on retry, so a replay carries the identical claim_token and the identical :now. Also confirmed the store does not depend on DynamoDB's best-effort TTL - takeover tests the item's own in_progress_expires_at.

Plan written; status left at To Do. Awaiting human review before implementation.
---
<!-- COMMENTS:END -->
