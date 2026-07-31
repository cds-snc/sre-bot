---
id: TASK-70
title: >-
  Adopt types-boto3 and google-api-python-client-stubs SDK stubs; wire the
  sdk-typing guardrails
status: To Do
assignee: []
created_date: '2026-07-31 16:54'
updated_date: '2026-07-31 17:49'
labels:
  - clients
  - phase-3
  - toolchain
milestone: m-3
dependencies:
  - TASK-19
references:
  - decisions/sdk-typing.md
  - decisions/outbound-clients.md
  - app/pyproject.toml
  - app/bin/check_deprecated_infra_client_imports.py
priority: high
ordinal: 110000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational enablement for the vendor-client convergence (decisions/sdk-typing.md, companion to decisions/outbound-clients.md). Establishes that a rich vendor SDK is typed WITHOUT a wrapper tier for BOTH vendor families in scope this sprint (AWS via boto3, Google Workspace via google-api-python-client), and makes the retired anti-patterns fail CI, so the AWS/Google surface migrations (TASK-22.2/22.3/22.4) can move consumers straight onto the target shape.

Scope: (1) add types-boto3 as a DEV-ONLY dependency scoped to the AWS services the app actually uses; confirm mypy/Pylance resolve a boto3 client handle's method signatures with zero wrappers. (2) add google-api-python-client-stubs as a DEV-ONLY dependency (a single unscoped package - no per-service extras exist for it, unlike types-boto3); confirm mypy/Pylance resolve discovery.build(service, version)'s return to a typed Resource (e.g. AdminDirectoryResource for admin/directory_v1) with real method/parameter/return signatures, for every discovery-based Google Workspace service the app uses today (admin/directory_v1, gmail_v1, drive_v3, docs_v1, sheets_v4 - grep infrastructure/clients/google_workspace/ and integrations/google_workspace/ to confirm the exact set at implementation). (3) Add a CI guardrail (same shape as TASK-19's deprecated-import freeze) that fails on net-new occurrences of the generic execute_aws_api_call/execute_google_api_call string-dispatch, __doc__-based parameter discovery, and per-vendor SDK-handle facade classes in integrations/. No consumer migration and no runtime behavior change for either vendor family.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 types-boto3 is a dev-only dependency scoped to the AWS services in use (dynamodb, identitystore, organizations, sso-admin, ce, guardduty, config, sqs, lambda); mypy resolves a session.client("dynamodb") handle's method signatures (e.g. get_item, query) with no wrapper and no new runtime dependency
- [ ] #2 google-api-python-client-stubs is a dev-only dependency (single unscoped package, no per-service extras); mypy resolves discovery.build("admin", "directory_v1") (and gmail_v1/drive_v3/docs_v1/sheets_v4) to a typed Resource with real method/parameter/return signatures, with no wrapper and no new runtime dependency
- [ ] #3 A CI guardrail (baseline that only ratchets down, mirroring TASK-19) fails on net-new execute_aws_api_call/execute_google_api_call string-dispatch or __doc__-based parameter discovery in app/integrations/
- [ ] #4 decisions/sdk-typing.md Checks that are enforceable today pass (types-boto3 present; google-api-python-client-stubs present; dispatcher/scraper guardrail live); the find "*_next.py"==0 and no-facade checks remain listed as tolerated divergences until TASK-23/TASK-22.5
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No runtime dependency added (both types-boto3 and google-api-python-client-stubs are dev-only / TYPE_CHECKING); PR references decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
CONTEXT: This is the enabling prerequisite for the resequenced client-convergence sprint (see decisions/sdk-typing.md, TASK-22 umbrella comment). It carries NO consumer migration and NO runtime behavior change; it makes the target pattern (typed SDK handle, no wrapper) available for BOTH AWS and Google Workspace, and makes the retired anti-patterns fail CI.

RESEQUENCED (2026-07-31, decisions/sdk-typing.md revision): the original version of this task was AWS-only. Research while planning TASK-22.4 found google-api-python-client-stubs, a community-maintained stub package that types googleapiclient.discovery.build()'s return the same way types-boto3 types a boto3 client - so the Google half of the sdk-typing.md contract is also a stub-adoption task, not a "stays untyped, only the adapter dataclass is typed" task. This task now delivers both stub adoptions side by side, since they are the same shape of enabling work and TASK-22.4 (Google Directory) needs this task's Google half exactly like TASK-22.2 (AWS DynamoDB) needs its AWS half.

STEP 1 - types-boto3 dev dependency:
- Add a dev/dependency group in app/pyproject.toml (a [dependency-groups] dev entry, matching how dev tooling like mypy/ruff/boto3_stubs is already declared) with `types-boto3[dynamodb,identitystore,organizations,sso-admin,ce,guardduty,config,sqs,lambda]` pinned compatibly with boto3>=1.42.54. Stubs are type-check-time only; they MUST NOT enter [project].dependencies (DoD#1). Note: app/pyproject.toml's dev group already has `boto3_stubs==1.42.54` (the predecessor package name to `types-boto3`) - verify at implementation whether to rename this pin to `types-boto3` or whether `boto3_stubs` already satisfies AC#1 as-is; do not add both.
- Remove the now-redundant `googleapiclient.*` / boto-related `ignore_missing_imports` override for boto ONLY where types-boto3 now supplies types (leave the googleapiclient override in place for STEP 1B to address). Do not touch other mypy overrides.
- Prove resolution: a tiny checked snippet (in a test or a mypy-run assertion) where `client: DynamoDBClient = boto3.session.Session().client("dynamodb")` and `client.get_item(TableName=..., Key=...)` type-checks with no wrapper. Import the stub name under TYPE_CHECKING (types_boto3_dynamodb) so runtime is untouched.

STEP 1B - google-api-python-client-stubs dev dependency (NEW, per the sdk-typing.md revision):
- Add `google-api-python-client-stubs` (unscoped, single package - it has no per-service extras mechanism like types-boto3) to the same `[dependency-groups] dev` entry, pinned to a specific version. Stubs are type-check-time only (`googleapiclient._apis.*`, invisible at runtime); MUST NOT enter [project].dependencies (DoD#1).
- Loosen (do not delete) the existing `googleapiclient.*` mypy `ignore_missing_imports` override only as far as the stub package's own caveats require (per its docs, stub types live under `googleapiclient._apis` and must be imported only under `if TYPE_CHECKING:` / with `from __future__ import annotations` - they do not exist at runtime and can crash code that evaluates annotations eagerly, e.g. Pydantic). Grep `infrastructure/clients/google_workspace/` and `integrations/google_workspace/` for every `build(service, version, ...)` call site to enumerate the exact discovery services in use (expected: admin/directory_v1, gmail_v1, drive_v3, docs_v1, sheets_v4) - this list is what TASK-22.4/TASK-25.2 will annotate.
- Prove resolution: a tiny checked snippet where `service: AdminDirectoryResource = build("admin", "directory_v1", credentials=creds, cache_discovery=False)` type-checks with real method-signature completion (e.g. `service.users().get(userKey=...)`), importing `AdminDirectoryResource` from `googleapiclient._apis.admin_directory_v1` only under `if TYPE_CHECKING:`. Repeat (or note as a follow-up check) for at least one non-directory service (e.g. gmail_v1) to confirm the stub package's coverage isn't directory-only.

STEP 2 - anti-pattern guardrail (mirror TASK-19's freeze check):
- Add app/bin/check_sdk_typing.py (sibling of bin/check_deprecated_infra_client_imports.py) + a hand-authored baseline app/bin/baselines/sdk_typing_antipatterns.txt capturing today's occurrences, in app/integrations/, of: (a) a generic dispatcher signature `def execute_aws_api_call`/`def execute_google_api_call` or call sites of them; (b) reflection dispatch `getattr(<resource>, method)()` keyed on a string method name; (c) `__doc__`-based parameter discovery (the get_google_api_command_parameters docstring scraper); (d) a class that stores an SDK handle and re-exposes its methods as passthroughs (the AWSClients-style facade shape). This single checker already covers both vendor families (it was never AWS-only) - no separate Google guardrail script is needed. Baseline only ratchets DOWN (net-new fails; shrinkage passes) exactly like TASK-19.
- Wire a blocking Make target (e.g. `check-sdk-typing`) and a CI step in .github/workflows/ci_code.yml next to the existing deprecated-import freeze step.
- Unit-test the checker under app/tests/unit/bin/ (detection + baseline shrink/growth paths), following test_check_deprecated_infra_client_imports.py.

STEP 3 - reconcile decisions/sdk-typing.md `applies`:
- The enforceable-now Checks (types-boto3 present; google-api-python-client-stubs present; dispatcher/scraper guardrail live) pass on main after this task. The `find "*_next.py"==0` and no-facade checks stay red until TASK-23/TASK-22.5 - those remain in the record's Migration/tolerated list (do NOT flip sdk-typing.md to applies:now here; it stays applies:target until the sprint completes).

AC-TO-STEP: AC#1 -> Step 1 (types-boto3 dev-only stub + mypy proof). AC#2 -> Step 1B (google-api-python-client-stubs dev-only stub + mypy proof, both directory and at least one non-directory service). AC#3 -> Step 2 (guardrail + CI, already vendor-agnostic). AC#4 -> Step 3 + Steps 1/1B/2. DoD#1 -> Steps 1/1B (no [project].dependencies change for either package) + PR text.

VALIDATION: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (must resolve both the dynamodb client snippet AND the admin/directory_v1 Resource snippet); cd app && uv run pytest tests/unit/bin -v; cd app && uv run ruff check .; run `make check-sdk-typing` locally and confirm exit 0 against the just-authored baseline, and that a scratch net-new dispatcher line (either execute_aws_api_call or execute_google_api_call) makes it exit 1.

BLAST RADIUS / ROLLBACK: additive tooling + two dev dependencies (types-boto3, google-api-python-client-stubs); no business logic, no runtime path, no terraform. Single git revert restores prior state. No ordering constraint vs TASK-18; must land before TASK-22.2 (consumes the AWS stub) and TASK-22.4 (consumes the Google stub).

SIZE GATE: ~1 pyproject block (two dev deps) + ~90 LOC checker (unchanged from original scope, already vendor-agnostic) + data-only baseline + ~6 Make/CI lines + one test file + two small mypy-proof snippets. Still well under the single-PR gate; the Google addition is a few lines of dependency + proof, not new tooling.

DOUBTS (verify at implementation): whether the repo's dev deps live in [dependency-groups] vs [tool.uv.dev-dependencies] (grep pyproject before editing - already confirmed [dependency-groups] at planning time); whether Pylance in-editor needs each stub installed in the active venv (it does for both - note in PR that `uv sync` including the dev group is required for editor resolution); whether `boto3_stubs==1.42.54` already in app/pyproject.toml should be renamed to `types-boto3` or left as-is (verify current PyPI relationship between the two names before editing - do not add a duplicate/conflicting pin); exact pin version for `google-api-python-client-stubs` and which Google services it covers (single package covers all discovery APIs bundled in google-api-python-client - confirm admin_directory_v1 and gmail_v1 are both present in the installed stub's namespace package before relying on it in TASK-22.4/TASK-25.2).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-31 17:49
---
RESEQUENCED (2026-07-31, second pass) after further research into Google Workspace SDK typing during TASK-22.2/22.4 planning. This task was originally scoped AWS-only (types-boto3), while decisions/sdk-typing.md's ORIGINAL text accepted the Google discovery Resource as permanently untyped. That decision was revised the same day: google-api-python-client-stubs (community-maintained, dev-only, same shape as types-boto3) types discovery.build()'s return per service+version, closing the asymmetry. sdk-typing.md's Migration section now names this task as delivering BOTH stub adoptions. This task's Description/AC/Plan were updated accordingly (added STEP 1B, new AC#2, renumbered AC#3/#4). No change to TASK-22.2/22.3 (AWS-only slices, unaffected) or TASK-23 (vendor-agnostic dispatcher deletion, unaffected). TASK-22.4 (Google Directory) and TASK-25.2 (Google remainder) both now depend on this task's Google half in addition to its AWS-derived AWS half.
---
<!-- COMMENTS:END -->
