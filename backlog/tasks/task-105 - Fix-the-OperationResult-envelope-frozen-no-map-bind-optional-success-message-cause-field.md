---
id: TASK-105
title: >-
  Fix the OperationResult envelope: frozen, no map/bind, optional success
  message, cause field
status: In Progress
assignee: []
created_date: '2026-09-24 19:57'
updated_date: '2026-09-28 15:37'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies: []
references:
  - decisions/operation-result.md
  - app/infrastructure/operations
priority: medium
type: task
ordinal: 245000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/operation-result.md lists envelope divergences to fix in one PR, independent of where the type lives. Fixing them in place before the move to app/contracts/ keeps the move purely mechanical (no refactor and behaviour change mixed in one PR).

Divergences (operation-result.md Consequences and Migration):
- the dataclass is mutable; the record requires frozen=True;
- map/bind monad helpers exist; the record removes them;
- message is required on SUCCESS; it becomes optional;
- there is no cause field (internal-only diagnostic, never rendered or serialized);
- undocumented provider/operation fields: keep and document, or drop, decided in this PR;
- a stale docstring points at the deleted ADR tree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 OperationResult is frozen=True and a unit test asserts immutability
- [x] #2 map and bind are removed and grep finds no .map( or .bind( call site on an OperationResult
- [x] #3 message is optional on SUCCESS; cause exists, is excluded from repr and serialization, and is never rendered
- [x] #4 The provider/operation fields are kept unchanged, with a docstring note that TASK-105.1 removes them
- [x] #5 The shared OperationResult renderer (SlackBlockKitFormatter.format_operation_result in app/integrations/slack/formatter.py -- the only cross-feature renderer that branches on OperationResult.status found in the codebase) is rewritten to match result.status: covering all five OperationStatus values plus typing.assert_never on the fall-through, preserving today's formatting behaviour (all non-SUCCESS statuses still render via format_error); mypy passes with no new errors in the touched files
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: fix the OperationResult envelope shape in place in app/infrastructure/operations/ only.
No move to app/contracts/ (TASK-106), no import-linter work (TASK-18), no classifier/status-enum
semantics change. Survey (codebase-researcher, 2026-09-28) found zero production callers of
.map/.bind/.unwrap/.unwrap_or (self-tested only) and zero mutation of OperationResult anywhere,
so frozen=True and removing the RoP surface are safe with no consumer fallout.

Stack A is now 18 -> 105 -> 105.1 -> 105.2 -> 106 (human-approved). TASK-105.1 removes
provider/operation and rewrites their ~12 call sites; TASK-105.2 builds the error-code StrEnum
registry. This task (105) therefore leaves provider/operation untouched functionally and does not
build the registry -- it only adds a short docstring note pointing at TASK-105.1.

Steps:

1. app/infrastructure/operations/result.py (production, ~150-200 LOC diff, the only functional file)
   - Module docstring: drop "Implements Railway-Oriented Programming..." and the stale
     "See: docs/decisions/tier-1-foundation/ADR-001-operation-result-pattern.md" line; point at
     decisions/operation-result.md instead.
   - `@dataclass` -> `@dataclass(frozen=True)`.
   - Remove `map()`, `bind()` (AC #2) and `unwrap()`, `unwrap_or()` (approved: same dead
     Railway-Oriented-Programming surface, zero production callers per survey). Drop the now-unused
     `Callable` import and `U = TypeVar("U")`.
   - `message: str` -> `message: str | None`; `success()`'s `message` parameter default changes from
     `"ok"` to `None` (AC #3, "message optional on SUCCESS"). `error()`, `transient_error()`,
     `permanent_error()` keep `message` required (non-success paths keep a mandatory message).
   - Add `cause: BaseException | None = field(default=None, repr=False, compare=False)`. `repr=False`
     satisfies "excluded from repr"; `compare=False` keeps equality assertions on error/success
     results working regardless of an attached exception. No code anywhere calls
     dataclasses.asdict/json.dumps/model_dump on an OperationResult (grepped, zero hits), so no
     extra "serialization" guard is needed beyond the type itself.
   - `retry_after: int | None` -> `retry_after: float | None` (approved), matching
     decisions/operation-result.md's canonical type. Purely additive: every current caller passes an
     int literal, and int is a valid float in Python/mypy's numeric tower, so no call-site changes.
   - `provider`/`operation` fields: leave the dataclass fields, factory kwargs and all ~12 call sites
     completely untouched. Add one short docstring line on each field: "Kept for observability;
     scheduled for removal in TASK-105.1, which is not part of the decisions/operation-result.md
     canonical shape." No other change.

2. app/integrations/slack/formatter.py (production, ~20-30 LOC diff)
   - `format_operation_result()`: replace `if result.status == OperationStatus.SUCCESS: ... else: ...`
     with `match result.status:` covering `SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`,
     `PERMANENT_ERROR`, `UNAUTHORIZED` explicitly, `case _ as unreachable: assert_never(unreachable)`
     on the fall-through, importing `assert_never` from `typing`. Every non-SUCCESS branch keeps
     calling `format_error(...)` exactly as today -- behaviour-preserving (AC #5). Note: this method
     has zero production callers today (survey); it's still the right target since it's the only
     reusable, cross-module renderer in the app that branches on `OperationResult.status`. The
     UNAUTHORIZED-vs-401/403 mapping gap in classify_http_error stays explicitly out of scope.

3. Tests (excluded from the size gate, edited in place -- pre-existing legacy files, not renamed):
   - app/tests/unit/infrastructure/test_operations_result.py:
     - Add a frozen/immutability test for AC #1 (`pytest.raises(dataclasses.FrozenInstanceError)`
       on attribute assignment).
     - Delete `TestOperationResultMap`, `TestOperationResultBind`, `TestOperationResultRailwayPattern`,
       `TestOperationResultUnwrapOr`, `TestOperationResultUnwrap` (methods removed in step 1).
     - Add tests: `OperationResult.success(data=...)` without `message=` yields `message is None`;
       `cause` round-trips through the constructor but is absent from `repr(result)`; equality between
       two otherwise-identical results holds regardless of differing `cause` values.
     - Leave `TestOperationResultObservability` as-is (provider/operation behaviour is unchanged).
   - app/tests/unit/integrations/slack/test_slack_formatter.py: extend the existing
     `format_operation_result` coverage with a parametrized case over all five `OperationStatus`
     values asserting the SUCCESS branch calls format_success-shaped output and the other four still
     produce the pre-existing format_error-shaped output (behaviour-preserving assertion for AC #5).
   - app/tests/unit/infrastructure/operations/test_classifiers.py: no code change expected; re-run as
     part of gate verification since it imports the touched result.py.

4. decisions/operation-result.md (documentation, same PR -- human-approved):
   - Decision section: `message: str` -> `message: str | None` (fixes the record's internal
     inconsistency with its own Migration section and this task's AC #3).
   - Migration section: remove the Consequences/Migration bullets for the divergences this PR closes
     (mutable dataclass, message required on success, stale docstring pointer) -- keep the
     provider/operation bullet as still-open (now pointing at TASK-105.1) and the contracts/-location
     tolerance (still open, closed by TASK-106).
   - Add a dated Changes entry, e.g.: "2026-09-28: TASK-105 froze the dataclass, removed
     map/bind/unwrap/unwrap_or, made message optional on success, added cause, and widened
     retry_after to float; provider/operation deferred to TASK-105.1."

AC traceability:
- AC #1 (frozen) -> step 1 (dataclass decorator) + new immutability test.
- AC #2 (map/bind removed, no call sites) -> step 1 (method removal) + deleted test classes + a
  grep verification (`rg -n '\.map\(|\.bind\('` over app/, excluding logger.bind/socket.bind, must
  return zero OperationResult hits) run as part of gate verification.
- AC #3 (message optional, cause field) -> step 1 (field/type changes) + new tests.
- AC #4 (provider/operation resolved and recorded) -> step 1 (docstring note referencing TASK-105.1)
  + task notes recording the choice at finalization.
- AC #5 (shared renderer, match + assert_never) -> step 2 + step 3's formatter test.
- AC #6 (gates) -> run `cd app && uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`,
  `uv run pytest tests --ignore=tests/smoke` and report actual output at finalization.

Assumptions to verify during implementation:
- No caller constructs `OperationResult(...)` positionally with more than the `status` argument
  (field order is left unchanged specifically to avoid this risk) -- spot-checked via the survey's
  construction-site sample, not exhaustively grepped for positional calls; re-grep
  `OperationResult(OperationStatus\.[A-Z_]+,` before merging if in doubt.
- The f-string sites that interpolate `.message` unconditionally (server/lifespan.py:175,218,223;
  integrations/maxmind/client.py:147; packages/access/common/providers.py:41;
  packages/access/sync/interactions/slack.py:209,302; packages/geolocate/platforms/slack.py:92;
  modules/aws/ops_group_assignment.py:37,60,77) are all gated behind `if not result.is_success:` /
  error-only branches (spot-checked lifespan.py and maxmind/client.py directly), so `message` is
  still guaranteed non-None there and needs no defensive `or "..."` guard. Re-check the remaining
  sites in this list during implementation if any turns out not to be error-gated.

Blast radius and rollback:
- Two production files plus one decision doc change; a `git revert` of the PR fully restores prior
  behaviour (no data migration, no persisted OperationResult instances).
- Widening `message`/`retry_after` types and adding `cause` are backward-compatible for the ~155
  files that import OperationResult/OperationStatus (import shape unchanged, no renames).
- Removing map/bind/unwrap/unwrap_or is a source-breaking change for any external/future caller,
  but survey confirms zero current callers outside the type's own tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the approved plan on stack-a/task-105-operation-result-envelope (Stack A layer 2).

Production: app/infrastructure/operations/result.py (frozen=True; map/bind/unwrap/unwrap_or, Callable/Any/TypeVar U removed; message: str | None with success() defaulting to None; cause: BaseException | None = field(default=None, repr=False, compare=False); retry_after: float | None; provider/operation kept with a docstring note pointing at TASK-105.1; docstring now points at decisions/operation-result.md). app/integrations/slack/formatter.py: format_operation_result uses match result.status with SUCCESS, an or-pattern over the four non-success statuses that still call format_error, and case _ -> assert_never.
Docs: decisions/operation-result.md (message: str | None in Decision; closed divergences removed from Consequences/Migration; 2026-09-28 Changes entry).
Tests: test_operations_result.py drops the Map/Bind/Unwrap/UnwrapOr/Railway classes and adds TestOperationResultEnvelopeShape (immutability, message None default, cause round trip, absent from repr, ignored by equality, float retry_after, helpers absent). test_slack_formatter.py parametrizes over all five statuses and adds a None-message error fallback test.

Gates: ruff check . -> All checks passed. ruff format --check -> clean. lint-imports -> 7 kept, 0 broken. pytest tests --ignore=tests/smoke -> 3500 passed, 6 failed, and all 6 are the known TASK-90 order leaks (test_webhooks_aws_sns.py, directory/test_google.py; 111 passed when rerun alone). make test -> 2749 + 757 passed. The CI freeze checks (fmt-ci, check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam, check-runtime-imports, check-import-contracts) all pass.
mypy: 0 errors in touched files. Against a HEAD baseline (79 -> 106), the widening adds 29 arg-type errors in 16 untouched files: 27 forward message: str | None, 2 forward float retry_after to int-typed legacy exceptions. The plan assumed both changes were additive, and it was wrong. CI does not block because lint-ci runs mypy with || true. The human chose to track them in the new subtask TASK-105.3 (depends on TASK-105.1) rather than widen this layer.
AC #2 grep: rg '\.(map|bind|unwrap|unwrap_or)\(' over app/ returns only structlog .bind() hits.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
