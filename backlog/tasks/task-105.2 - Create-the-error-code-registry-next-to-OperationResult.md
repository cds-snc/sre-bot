---
id: TASK-105.2
title: Create the error-code registry next to OperationResult
status: In Progress
assignee: []
created_date: '2026-09-28 14:35'
updated_date: '2026-09-28 16:05'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies:
  - TASK-105.1
references:
  - decisions/operation-result.md
  - backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md
parent_task_id: TASK-105
priority: medium
ordinal: 284000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/operation-result.md says error_code is drawn from the project registry: an enum-like module next to the dataclass, where adding a code is a reviewed one-line change. No registry exists today.

Verified survey (2026-09-28, codebase-researcher plus direct grep across app/ excluding app/tests and .venv): 75 distinct SCREAMING_SNAKE error_code values are in live use, reached three ways -- (1) `error_code="LITERAL"` keyword literals at call sites (packages/access/request/service.py, infrastructure/directory/google.py, packages/access/sync/adapters/aws_identity_center.py, integrations/openai/client.py, integrations/slack/provider.py, packages/access/common/config/loaders.py, packages/access/sync/adapters/fake_platform.py, integrations/maxmind/client.py, packages/access/sync/desired_state.py, packages/access/sync/application.py, packages/geolocate/service.py, packages/access/sync/interactions/ingress.py, packages/access/catalog/service.py); (2) same-module SCREAMING_SNAKE constants (RANGE_NOT_FOUND in infrastructure/spreadsheets/google.py; DOCUMENT_UNREADABLE_CODE, EMPTY_HISTORY_CODE, DRAFT_UNPARSEABLE_CODE, NO_ANSWERS_CODE, CREATE_FAILED_CODE in packages/incident_draft/service.py, the last independently redefined in packages/incident_summary/service.py); (3) fully-enumerable classifier branching in classify_openai_error (integrations/openai/client.py) and classify_maxmind_error (integrations/maxmind/client.py, contributing IP_NOT_FOUND, INVALID_IP_FORMAT, GEOIP2_ERROR), plus one literal-fallback `or` expression (packages/access/catalog/service.py:158, `error_code=discovery_result.error_code or "GROUP_DISCOVERY_FAILED"`). No production call site ever passes error_code positionally.

TASK-105.1 (this task's dependency) deletes app/infrastructure/operations/classifiers.py outright -- verified it has no production caller today, only its own __init__ re-export and its own tests. Its three functions (classify_http_error, the operations-layer classify_aws_error, classify_integration_error) are therefore not a code source for this registry. Four codes were produced only there with no other live producer and are dropped from the seed list: UNKNOWN_ERROR, INVALID_REQUEST, AWS_CLIENT_ERROR, INTEGRATION_ERROR. The overlapping codes classifiers.py shared with integrations/openai/client.py's classify_openai_error (CONNECTION_ERROR, RATE_LIMITED, UNAUTHORIZED, FORBIDDEN, NOT_FOUND, SERVER_ERROR, HTTP_ERROR) stay in the registry because openai's classifier still produces them.

Two further code-producing mechanisms exist but are explicitly OUT OF SCOPE for this SCREAMING_SNAKE registry (a later, separate task owns reconciling them with the ADR): `integrations/aws/client.py::classify_aws_error` (a second, differently-scoped function, unrelated to the deleted operations-layer one) returns raw botocore PascalCase error codes sourced from a runtime-configurable settings catalogue (integrations/aws/settings.py AWSSettings.NOT_FOUND_CODES/UNAUTHORIZED_CODES/TRANSIENT_CODES) or `type(exc).__name__` for unmatched BotoCoreError subclasses (statically unbounded); `integrations/google_workspace/client.py::classify_google_error` returns `str(http_status)` numeric strings.

Roughly 90 further sites only ever copy an already-classified error_code through (`error_code=result.error_code`, exception-carried and even JSON round-tripped in legacy app/modules/), introducing no new codes; the enforcement test must not fail on these.

decisions/operation-result.md additionally requires UNAUTHENTICATED as the error_code that, with FORBIDDEN, distinguishes UNAUTHORIZED (AC #4); UNAUTHENTICATED has zero call sites today (only the generic "UNAUTHORIZED" and "FORBIDDEN" literals exist), so the registry adds it as a 76th member ahead of any caller using it.

TASK-106 moves the registry to app/contracts/, so it must exist first. Stack A layer between TASK-105.1 and TASK-106 (doc-2). Create the registry in app/infrastructure/operations/ as a StrEnum seeded with all 76 SCREAMING_SNAKE codes (75 in current use plus UNAUTHENTICATED), plus a test that fails on an unregistered error_code literal or resolvable same-module constant. Existing callers keep their string literals (StrEnum members compare equal to str), so no call site changes in this layer; migrating callers to registry members, splitting the generic UNAUTHORIZED/FORBIDDEN literal, and reconciling the two non-SCREAMING_SNAKE AWS/Google classifiers with the ADR are later ratchets, not this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/operations/ exposes an error-code registry (StrEnum) containing every SCREAMING_SNAKE error_code value produced by production code today, after TASK-105.1 deletes classifiers.py (the AWS-raw and Google-numeric-status codes in integrations/aws/client.py and integrations/google_workspace/client.py are a separate, non-SCREAMING_SNAKE scheme and are explicitly out of scope)
- [x] #2 A test scans production code and fails when a static SCREAMING_SNAKE error_code literal (or same-module constant) is not a registry member; the test is green on this PR
- [x] #3 No production call site changes; behaviour is unchanged
- [x] #4 The registry covers UNAUTHENTICATED and FORBIDDEN as the error_code pair that distinguishes UNAUTHORIZED, per decisions/operation-result.md
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: add an error-code registry next to OperationResult in app/infrastructure/operations/
and a deterministic enforcement test. No call-site changes, no move to app/contracts/
(TASK-106), no import-linter work (TASK-18), no splitting of the generic UNAUTHORIZED/
FORBIDDEN literal, no reconciling of the two non-SCREAMING_SNAKE AWS/Google classifiers with
the ADR (all later ratchets). Assumes TASK-105.1 has already deleted
app/infrastructure/operations/classifiers.py (verified: zero production callers today, only
its own __init__ re-export and its own tests) -- this task's registry does not seed from that
module.

Survey (codebase-researcher plus direct grep/read, 2026-09-28, app/ excluding app/tests and
.venv) -- see task description for the full narrative. Summary used to build this plan:
- 75 distinct SCREAMING_SNAKE error_code values in live use once classifiers.py is gone,
  reached via: keyword literals (packages/access/request/service.py, infrastructure/directory/
  google.py, packages/access/sync/adapters/aws_identity_center.py, integrations/openai/
  client.py, integrations/slack/provider.py, packages/access/common/config/loaders.py,
  packages/access/sync/adapters/fake_platform.py, integrations/maxmind/client.py, packages/
  access/sync/desired_state.py, packages/access/sync/application.py, packages/geolocate/
  service.py, packages/access/sync/interactions/ingress.py, packages/access/catalog/
  service.py); same-module SCREAMING_SNAKE constants (RANGE_NOT_FOUND in infrastructure/
  spreadsheets/google.py; DOCUMENT_UNREADABLE_CODE, EMPTY_HISTORY_CODE, DRAFT_UNPARSEABLE_CODE,
  NO_ANSWERS_CODE, CREATE_FAILED_CODE in packages/incident_draft/service.py, EMPTY_HISTORY_CODE
  independently redefined in packages/incident_summary/service.py); fully enumerable classifier
  branching in classify_openai_error (integrations/openai/client.py) and classify_maxmind_error
  (integrations/maxmind/client.py, contributing IP_NOT_FOUND, INVALID_IP_FORMAT, GEOIP2_ERROR);
  one literal-fallback `or` expression (packages/access/catalog/service.py:158,
  `error_code=discovery_result.error_code or "GROUP_DISCOVERY_FAILED"`).
- Dropped from the seed list because their only producer was the now-deleted
  infrastructure/operations/classifiers.py, confirmed via grep with zero hits elsewhere:
  UNKNOWN_ERROR, INVALID_REQUEST, AWS_CLIENT_ERROR, INTEGRATION_ERROR. Kept despite classifiers.py
  also producing them, because integrations/openai/client.py's classify_openai_error
  independently produces them too: CONNECTION_ERROR, RATE_LIMITED, UNAUTHORIZED, FORBIDDEN,
  NOT_FOUND, SERVER_ERROR, HTTP_ERROR.
- Explicitly OUT OF SCOPE (not SCREAMING_SNAKE, do not add to this registry, do not let the
  enforcement test touch): integrations/aws/client.py::classify_aws_error (unrelated to the
  deleted operations-layer function of the same name) returns raw botocore PascalCase codes
  from the runtime-configurable integrations/aws/settings.py AWSSettings catalogue, or
  `type(exc).__name__` for unmatched BotoCoreError subclasses (statically unbounded);
  integrations/google_workspace/client.py::classify_google_error returns `str(http_status)`
  numeric strings. Neither assigns its output via a literal `error_code="SCREAMING_SNAKE"`
  keyword, so the AST scan in step 3 naturally never touches them -- no exclusion logic needed,
  just documented so a reviewer doesn't expect them covered by AC #1.
- ~90 sites only copy an already-classified error_code through (`error_code=result.error_code`,
  exception-carried, some JSON round-tripped in legacy app/modules/); these introduce no new
  codes and must not trip the enforcement test.
- No positional error_code arguments anywhere in production code (result.py's factory
  signatures take error_code 3rd/2nd positional depending on method, but every production call
  uses the keyword form).
- mypy: OperationResult.error_code is `str | None`; `enum.StrEnum` members are `str` instances
  (verified: `isinstance(Codes.X, str)` and `Codes.X == "X"` are both True on this repo's
  Python 3.14), so no mypy or behaviour impact anywhere -- confirms AC #3.

Steps:

1. app/infrastructure/operations/codes.py (new, production, ~95 LOC)
   - Module docstring referencing decisions/operation-result.md: adding a code here is the
     one-line reviewed change the ADR requires; call sites are not required to import this
     enum (plain string literals remain valid; StrEnum equality makes both forms equivalent);
     note that the AWS-raw and Google-numeric-status codes are a separate scheme and
     intentionally excluded.
   - `from enum import StrEnum`.
   - `class ErrorCode(StrEnum):` with one member per line, `NAME = "NAME"`, alphabetically
     sorted, all 76 codes (75 in use today + UNAUTHENTICATED):
     ACTOR_AUTHORIZATION_CHECK_FAILED, ADAPTER_NOT_FOUND, ALREADY_PROVISIONED,
     AMBIGUOUS_GROUP_NAME, APPROVER_NOT_AUTHORIZED, CANCELLATION_NOT_AUTHORIZED,
     CONFIG_INVALID_JSON, CONFIG_INVALID_SHAPE, CONFIG_NOT_CONFIGURED, CONFIG_NOT_FOUND,
     CONFIG_READ_FAILED, CONNECTION_ERROR, CREATE_FAILED, DB_FILE_ERROR,
     DELEGATED_ACTOR_NOT_AUTHORIZED, DIRECTORY_GROUPS_PAYLOAD_INVALID,
     DIRECTORY_GROUP_DOMAIN_MISMATCH, DIRECTORY_GROUP_EMAIL_REQUIRED,
     DIRECTORY_GROUP_ID_REQUIRED, DIRECTORY_GROUP_PAYLOAD_INVALID,
     DIRECTORY_MEMBERSHIP_PAYLOAD_INVALID, DIRECTORY_MEMBERS_PAYLOAD_INVALID,
     DIRECTORY_MEMBER_EMAIL_REQUIRED, DIRECTORY_MEMBER_PAYLOAD_INVALID,
     DIRECTORY_MEMBER_TYPES_INVALID, DIRECTORY_USERS_PAYLOAD_INVALID,
     DIRECTORY_USER_EMAIL_REQUIRED, DIRECTORY_USER_GROUPS_PAYLOAD_INVALID,
     DIRECTORY_USER_ID_REQUIRED, DIRECTORY_USER_MAPPING_INVALID, DOCUMENT_UNREADABLE,
     DRAFT_UNPARSEABLE, EMPTY_HISTORY, ENTITLEMENT_MODE_DEACTIVATED, ENTITLEMENT_MODE_EPHEMERAL,
     FEATURE_DISABLED, FORBIDDEN, GEOIP2_ERROR, GROUP_DISCOVERY_FAILED, GROUP_ID_NOT_FOUND,
     GROUP_NOT_FOUND, HEALTHCHECK_FAILED, HTTP_ERROR, IDP_WRITE_FAILED, INITIALIZATION_ERROR,
     INVALID_AWS_RESPONSE, INVALID_ENTITLEMENT_ID, INVALID_GROUP_INDEX, INVALID_IP_FORMAT,
     INVALID_PLANNED_ACTION, INVALID_STATE_TRANSITION, IP_NOT_FOUND, MISSING_APP_TOKEN,
     MISSING_BOT_TOKEN, NOT_FOUND, NOT_PROVISIONED, NO_ANSWERS, NO_APPROVERS_FOUND,
     PLATFORM_NOT_FOUND, POLICY_NOT_FOUND, PROVIDER_DISABLED, RANGE_NOT_FOUND, RATE_LIMITED,
     REQUEST_NOT_FOUND, SELF_APPROVAL_DENIED, SERVER_ERROR, SOCKET_MODE_HANDLER_MISSING,
     SOCKET_MODE_START_FAILED, TIMEOUT, UNAUTHENTICATED, UNAUTHORIZED, UNEXPECTED_ERROR,
     UNKNOWN_ACTION, UNSUPPORTED_ENTITLEMENT_TYPE, UNSUPPORTED_OPERATION, USER_NOT_FOUND.
   - No changes to result.py or status.py (AC #1, #3): ErrorCode is additive, error_code stays
     `str | None` so existing string-literal call sites remain valid without import changes.

2. app/infrastructure/operations/__init__.py (production, ~2 LOC)
   - Import `ErrorCode` from `infrastructure.operations.codes` and add it to `__all__`. By the
     time this task lands, TASK-105.1 will already have removed this module's
     classify_http_error/classify_aws_error/classify_integration_error imports and __all__
     entries (classifiers.py deleted); this step only adds the ErrorCode export alongside
     whatever TASK-105.1 leaves behind (OperationResult, OperationStatus). Only edit outside
     the new file, keeping the diff mechanical.

3. app/tests/unit/infrastructure/operations/test_error_code_registry.py (new test file,
   ~90-110 LOC; directory already exists)
   - Enforcement test (AC #2), following this repo's existing AST-based boundary-test
     convention (see app/tests/unit/packages/geolocate/test_service_import_boundaries.py):
     a. Walk `Path(__file__).resolve().parents[4]` (app/ root) for `*.py`, excluding paths
        under `tests/`, `.venv/`, `__pycache__/`, `.mypy_cache/`. Deterministic: pure
        filesystem walk + `ast.parse`, no imports, no network, ~356 files, sub-second.
     b. Per file, `ast.parse` once. First pass: collect module-level `NAME = "STRING"`
        assignments (`ast.Assign` at module scope, single `ast.Name` target, `ast.Constant`
        str value) into a per-file constant map -- resolves the module-constant pattern
        (RANGE_NOT_FOUND, the *_CODE constants).
     c. Second pass: `ast.walk` for every `ast.keyword` node with `arg == "error_code"`
        anywhere in the file (not restricted to OperationResult calls -- this also correctly
        no-ops on the exception-carried and logger-kwarg pass-through sites, since their values
        are never literal). For each keyword's `.value` node:
        - `ast.Constant` str -> collect as a code to check.
        - `ast.Name` resolvable via the file's constant map from (b) -> collect its value.
        - `ast.BoolOp` (the `x or "LITERAL"` fallback pattern) -> recurse into `.values`,
          collecting any `ast.Constant` str operand, skipping the rest.
        - anything else (`ast.Attribute` like `result.error_code`, `ast.Call` like
          `metadata.get(...)`, `ast.Subscript`, `None`, a bare parameter) -> skip; not
          statically resolvable. This is the deliberate, documented boundary of static
          enforcement in this ratchet.
     d. Assert the set of resolved codes not in `{member.value for member in ErrorCode}` is
        empty; failure message lists each offending `path:line:code`. This single assertion
        already fails if a currently-registered, in-use code is ever removed from the enum (the
        scan would re-detect it as unregistered), so no separate regression-guard test
        re-enumerating all 75 in-use codes is needed -- it would only duplicate the enum.
   - A second test asserts `ErrorCode.UNAUTHENTICATED` and `ErrorCode.FORBIDDEN` are both
     registry members (AC #4) -- kept because UNAUTHENTICATED has no live producer today, so
     the AST scan alone would never exercise it.

AC traceability:
- AC #1 (registry exposes every SCREAMING_SNAKE error_code in use post-TASK-105.1; AWS-raw/
  Google-numeric schemes explicitly excluded) -> step 1 (76-member StrEnum).
- AC #2 (test fails on an unregistered static literal, green today) -> step 3's AST-scan test.
- AC #3 (no call-site changes) -> steps 1-2 touch only new/registry files; mypy compatibility
  confirmed above; no other file edited.
- AC #4 (UNAUTHENTICATED/FORBIDDEN pair) -> step 1 (both members present) + step 3's pair test.
- AC #5 (gates) -> run `cd app && uv run ruff check .`,
  `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, the project's configured import-linter
  invocation, and `uv run pytest tests --ignore=tests/smoke`; report actual output at
  finalization.

Assumptions to verify during implementation:
- TASK-105.1 has merged (or at least its classifiers.py deletion is in the working tree) before
  this task's registry is seeded, so the four classifiers-only codes stay excluded; if TASK-105.1
  lands with classifiers.py kept for any reason, re-add UNKNOWN_ERROR/INVALID_REQUEST/
  AWS_CLIENT_ERROR/INTEGRATION_ERROR to the registry before merging this task.
- Step 3b's module-constant resolution is same-file only; it does not follow constants imported
  from another module. No cross-module error_code constant import exists today (surveyed); if
  one appears later without updating the scan, the test silently skips it rather than failing --
  acceptable for this ratchet, revisit if it happens.
- No new production dependency on `ErrorCode` is introduced; migrating callers is explicitly
  deferred per the task description ("a later ratchet, not this task").
- The AWS-raw and Google-numeric-status classifiers are confirmed to never assign their output
  via a literal `error_code="SCREAMING_SNAKE"` keyword, so they cannot trip the scan; re-grep
  `error_code\s*=\s*"[A-Z]` in integrations/aws/client.py and integrations/google_workspace/
  client.py before merging if in doubt.

Blast radius and rollback:
- One new production file, a 2-line `__init__.py` addition, one new test file; a `git revert`
  fully restores prior behaviour with zero runtime impact (registry is additive and
  unreferenced by existing call sites).
- Single subsystem (app/infrastructure/operations/), well under the size gate: ~2 production
  files (~95 LOC) plus 1 new test file.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented on stack-a/task-105.2-error-code-registry (Stack A layer 4).

- app/infrastructure/operations/codes.py: ErrorCode(StrEnum), 76 members, alphabetical, NAME = "NAME". Exported from infrastructure.operations.
- Seed verified against the AST scan: 73 codes are found statically, GEOIP2_ERROR and IP_NOT_FOUND come from classify_maxmind_error's returned tuple (not an error_code= keyword), and UNAUTHENTICATED has no producer yet. That accounts for all 76; no over-seeding.
- MISSING_APP_TOKEN and MISSING_BOT_TOKEN carry an inline '# noqa: S105 -- error-code name, not a credential', following the precedent in packages/access/common/config/{settings,loaders}.py.
- app/tests/unit/infrastructure/operations/test_error_code_registry.py: production scan (literals, same-module constants, or-fallback operands; pass-through values skipped), a resolver test on an inline snippet so the scan cannot pass vacuously (added beyond the plan), and the UNAUTHENTICATED/FORBIDDEN pair test.
- No call sites changed.

Gates (from app/): ruff check . -> All checks passed; lint-imports -> 7 kept, 0 broken; mypy -> 102 errors in 37 files repo-wide, 0 in touched files; pytest tests --ignore=tests/smoke -> 3468 passed, 6 failed (the known single-process order leaks in test_webhooks_aws_sns.py and directory/test_google.py; those two files alone: 111 passed); make test -> 2717 passed + 757 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
