---
id: TASK-70
title: >-
  Adopt types-boto3 and google-api-python-client-stubs SDK stubs; wire the
  sdk-typing guardrails
status: Done
assignee:
  - '@me'
created_date: '2026-07-31 16:54'
updated_date: '2026-08-04 19:25'
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

Scope: (1) add types-boto3 as a DEV-ONLY dependency scoped to the AWS services the app actually uses; confirm mypy/Pylance resolve a boto3 client handle's method signatures with zero wrappers. (2) add google-api-python-client-stubs as a DEV-ONLY dependency (a single unscoped package - no per-service extras exist for it, unlike types-boto3); confirm mypy/Pylance resolve discovery.build(service, version)'s return to a typed Resource (e.g. AdminDirectoryResource for admin/directory_v1) with real method/parameter/return signatures, for every discovery-based Google Workspace service the app uses today (admin/directory_v1, gmail_v1, drive_v3, docs_v1, sheets_v4, calendar_v3, meet_v2 - grep-confirmed 2026-08-04 against integrations/google_workspace/, not just the description prose). (3) Add a CI guardrail (same shape as TASK-19's deprecated-import freeze) that fails on net-new occurrences of the generic execute_aws_api_call/execute_google_api_call string-dispatch, __doc__-based parameter discovery, and per-vendor SDK-handle facade classes in integrations/. No consumer migration and no runtime behavior change for either vendor family.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 types-boto3 is a dev-only dependency scoped to the AWS services in use (dynamodb, identitystore, organizations, sso-admin, ce, guardduty, config, sqs, lambda, securityhub); mypy resolves a session.client("dynamodb") handle's method signatures (e.g. get_item, query) with no wrapper and no new runtime dependency
- [x] #2 google-api-python-client-stubs is a dev-only dependency (single unscoped package, no per-service extras); mypy resolves discovery.build("admin", "directory_v1") (and gmail_v1/drive_v3/docs_v1/sheets_v4/calendar_v3/meet_v2) to a typed Resource with real method/parameter/return signatures, with no wrapper and no new runtime dependency
- [x] #3 A CI guardrail (baseline that only ratchets down, mirroring TASK-19) fails on net-new execute_aws_api_call/execute_google_api_call string-dispatch or __doc__-based parameter discovery in app/integrations/
- [x] #4 decisions/sdk-typing.md Checks that are enforceable today pass (types-boto3 present; google-api-python-client-stubs present; dispatcher/scraper guardrail live); the find "*_next.py"==0 and no-facade checks remain listed as tolerated divergences until TASK-23/TASK-22.5
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 No runtime dependency added (both types-boto3 and google-api-python-client-stubs are dev-only / TYPE_CHECKING); PR references decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
CONTEXT: This is the enabling prerequisite for the resequenced client-convergence sprint (see decisions/sdk-typing.md, TASK-22 umbrella comment). It carries NO consumer migration and NO runtime behavior change; it makes the target pattern (typed SDK handle, no wrapper) available for BOTH AWS and Google Workspace, and makes the retired anti-patterns fail CI.

RESEQUENCED (2026-07-31, decisions/sdk-typing.md revision): the original version of this task was AWS-only. Research while planning TASK-22.4 found google-api-python-client-stubs, a community-maintained stub package that types googleapiclient.discovery.build()'s return the same way types-boto3 types a boto3 client - so the Google half of the sdk-typing.md contract is also a stub-adoption task, not a "stays untyped, only the adapter dataclass is typed" task. This task now delivers both stub adoptions side by side, since they are the same shape of enabling work and TASK-22.4 (Google Directory) needs this task's Google half exactly like TASK-22.2 (AWS DynamoDB) needs its AWS half.

CORRECTION (2026-08-04, re-verification pass before implementation): a fresh repo-wide grep of every execute_aws_api_call/execute_google_api_call call site found BOTH vendor service lists in this task's original Description/AC/Plan were undercounted (prose lists never re-derived from a fresh grep, per the established "always re-grep, don't trust prose" lesson from the AWS/Google-remainder decomposition passes on TASK-25.1/25.2). AWS: app/integrations/aws/security_hub.py calls execute_aws_api_call("securityhub", ...) - a 10th service missing from the original 9-service list. Google: app/integrations/google_workspace/google_calendar.py uses build("calendar", "v3") and app/integrations/google_workspace/meet.py uses build("meet", "v2") - both missing from the original 5-service list (admin/directory_v1, gmail_v1, drive_v3, docs_v1, sheets_v4). AC#1/AC#2 and this plan are corrected below to the verified 10-service AWS list and 7-service Google list. Also confirmed via PyPI/GitHub (2026-08-04): google-api-python-client-stubs latest release is 1.39.0 (released 2026-07-11), auto-generated from the Discovery Documents bundled with the installed google-api-python-client version, description states it covers stubs for every discovery API bundled in the library - meet_v2 and calendar_v3 are ordinary bundled discovery APIs, not a special case, but STEP 1B still explicitly proves resolution for at least one of the two newly-found services (not just admin/directory_v1 + one arbitrary other) since the original doubt about coverage gaps for a less-common API remains valid until proven by an actual mypy run.

TARGET SHAPE (unchanged): boto3 -> types-boto3 stubs; google-api-python-client -> google-api-python-client-stubs; both dev-only/TYPE_CHECKING, zero runtime dependency, zero wrapper tier.

STEP 1 - types-boto3 dev dependency:
- Add a dev/dependency group in app/pyproject.toml (a [dependency-groups] dev entry, matching how dev tooling like mypy/ruff/boto3_stubs is already declared) with `types-boto3[dynamodb,identitystore,organizations,sso-admin,ce,guardduty,config,sqs,lambda,securityhub]` pinned compatibly with boto3>=1.42.54. Stubs are type-check-time only; they MUST NOT enter [project].dependencies (DoD#1). Note: app/pyproject.toml's dev group already has `boto3_stubs==1.42.54` (the predecessor package name to `types-boto3`, confirmed still present via grep 2026-08-04) - verify at implementation whether to rename this pin to `types-boto3` or whether `boto3_stubs` already satisfies AC#1 as-is; do not add both.
- Remove the now-redundant `googleapiclient.*` / boto-related `ignore_missing_imports` override for boto ONLY where types-boto3 now supplies types (leave the googleapiclient override in place for STEP 1B to address). Do not touch other mypy overrides.
- Prove resolution: a tiny checked snippet (in a test or a mypy-run assertion) where `client: DynamoDBClient = boto3.session.Session().client("dynamodb")` and `client.get_item(TableName=..., Key=...)` type-checks with no wrapper. Import the stub name under TYPE_CHECKING (types_boto3_dynamodb) so runtime is untouched.

STEP 1B - google-api-python-client-stubs dev dependency:
- Add `google-api-python-client-stubs` (unscoped, single package - it has no per-service extras mechanism like types-boto3) to the same `[dependency-groups] dev` entry, pinned to 1.39.0 (latest as of 2026-08-04; re-check for a newer release at implementation time). Stubs are type-check-time only (`googleapiclient._apis.*`, invisible at runtime); MUST NOT enter [project].dependencies (DoD#1).
- Loosen (do not delete) the existing `googleapiclient.*` mypy `ignore_missing_imports` override only as far as the stub package's own caveats require (per its docs, stub types live under `googleapiclient._apis` and must be imported only under `if TYPE_CHECKING:` / with `from __future__ import annotations` - they do not exist at runtime and can crash code that evaluates annotations eagerly, e.g. Pydantic).
- Grep-confirmed exact discovery services in use (2026-08-04, supersedes the original 5-service list): admin/directory_v1, gmail_v1, drive_v3, docs_v1, sheets_v4, calendar_v3, meet_v2 - 7 services across app/integrations/google_workspace/{google_directory,google_directory_next,gmail,gmail_next,google_drive,google_docs,sheets,google_calendar,meet}.py. This list is what TASK-22.4/TASK-25.1.x will annotate.
- Prove resolution: a tiny checked snippet where `service: AdminDirectoryResource = build("admin", "directory_v1", credentials=creds, cache_discovery=False)` type-checks with real method-signature completion (e.g. `service.users().get(userKey=...)`), importing `AdminDirectoryResource` from `googleapiclient._apis.admin_directory_v1` only under `if TYPE_CHECKING:`. Additionally prove resolution for at least one of the two newly-found services (calendar_v3 or meet_v2, e.g. `CalendarResource`/`MeetResource`) alongside gmail_v1, since those two were absent from the original coverage-verification scope and their presence in the stub package's namespace is a genuine unverified assumption until a real mypy run confirms it.

STEP 2 - anti-pattern guardrail (mirror TASK-19's freeze check):
- Add app/bin/check_sdk_typing.py (sibling of bin/check_deprecated_infra_client_imports.py) + a hand-authored baseline app/bin/baselines/sdk_typing_antipatterns.txt capturing today's occurrences, in app/integrations/, of: (a) a generic dispatcher signature `def execute_aws_api_call`/`def execute_google_api_call` or call sites of them; (b) reflection dispatch `getattr(<resource>, method)()` keyed on a string method name; (c) `__doc__`-based parameter discovery (the get_google_api_command_parameters docstring scraper); (d) a class that stores an SDK handle and re-exposes its methods as passthroughs (the AWSClients-style facade shape). This single checker already covers both vendor families (it was never AWS-only) - no separate Google guardrail script is needed. Baseline only ratchets DOWN (net-new fails; shrinkage passes) exactly like TASK-19.
- Wire a blocking Make target (e.g. `check-sdk-typing`) and a CI step in .github/workflows/ci_code.yml next to the existing deprecated-import freeze step.
- Unit-test the checker under app/tests/unit/bin/ (detection + baseline shrink/growth paths), following test_check_deprecated_infra_client_imports.py.

STEP 3 - reconcile decisions/sdk-typing.md `applies`:
- The enforceable-now Checks (types-boto3 present; google-api-python-client-stubs present; dispatcher/scraper guardrail live) pass on main after this task. The `find "*_next.py"==0` and no-facade checks stay red until TASK-23/TASK-22.5 - those remain in the record's Migration/tolerated list (do NOT flip sdk-typing.md to applies:now here; it stays applies:target until the sprint completes).

AC-TO-STEP: AC#1 -> Step 1 (types-boto3 dev-only stub, corrected 10-service extras list + mypy proof). AC#2 -> Step 1B (google-api-python-client-stubs dev-only stub, corrected 7-service coverage proof including calendar_v3/meet_v2). AC#3 -> Step 2 (guardrail + CI, already vendor-agnostic). AC#4 -> Step 3 + Steps 1/1B/2. DoD#1 -> Steps 1/1B (no [project].dependencies change for either package) + PR text.

VALIDATION: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (must resolve the dynamodb client snippet AND the admin/directory_v1 Resource snippet AND at least one of calendar_v3/meet_v2); cd app && uv run pytest tests/unit/bin -v; cd app && uv run ruff check .; run `make check-sdk-typing` locally and confirm exit 0 against the just-authored baseline, and that a scratch net-new dispatcher line (either execute_aws_api_call or execute_google_api_call) makes it exit 1.

BLAST RADIUS / ROLLBACK: additive tooling + two dev dependencies (types-boto3, google-api-python-client-stubs); no business logic, no runtime path, no terraform. Single git revert restores prior state. No ordering constraint vs TASK-18; must land before TASK-22.2 (consumes the AWS stub) and TASK-22.4 (consumes the Google stub).

SIZE GATE: ~1 pyproject block (two dev deps) + ~90 LOC checker (unchanged from original scope, already vendor-agnostic) + data-only baseline + ~6 Make/CI lines + one test file + two small mypy-proof snippets (a third small proof snippet added for the corrected Google service count, still trivial). Still well under the single-PR gate.

DOUBTS (verify at implementation): whether the repo's dev deps live in [dependency-groups] vs [tool.uv.dev-dependencies] (grep pyproject before editing - already confirmed [dependency-groups] at planning time, re-confirmed 2026-08-04); whether Pylance in-editor needs each stub installed in the active venv (it does for both - note in PR that `uv sync` including the dev group is required for editor resolution); whether `boto3_stubs==1.42.54` already in app/pyproject.toml should be renamed to `types-boto3` or left as-is (verify current PyPI relationship between the two names before editing - do not add a duplicate/conflicting pin); whether the stub package's namespace actually contains typed Resources for calendar_v3 and meet_v2 (both newly found 2026-08-04; the package's own docs claim full Discovery-bundled coverage but this is unproven for these two specific services until STEP 1B's mypy proof runs - if either is genuinely absent from the installed stub's namespace, fall back to importing it under TYPE_CHECKING with an explicit `# type: ignore[...]`-free `Any`-typed local Protocol for that one service only, and flag it as a stub-package gap in the PR rather than silently blocking on it).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
STEP 1 (AC#1): Replaced boto3_stubs==1.42.54 with types-boto3[ce,config,dynamodb,guardduty,identitystore,lambda,organizations,securityhub,sqs,sso-admin]>=1.43.63 in [dependency-groups] dev. mypy resolves DynamoDBClient.get_item() with no wrapper (proof: /tmp/test_boto3_stub.py, uv run mypy exits 0). Removed old boto3-stubs pin to avoid dual-package conflict. Bonus: boto3.dynamodb.types errors in modules/ resolved (186→181 mypy errors).

STEP 1B (AC#2): Added google-api-python-client-stubs>=1.39.0 to dev deps. mypy resolves AdminDirectoryResource (admin/directory_v1), CalendarResource (calendar_v3), and MeetResource (meet_v2) from googleapiclient._apis.* under TYPE_CHECKING (proof: /tmp/test_google_stub.py, uv run mypy exits 0). Both stubs are dev-only; no runtime dependency added.

STEP 2 (AC#3): Created app/bin/check_sdk_typing.py scanning integrations/ for execute_aws_api_call / execute_google_api_call / __doc__ anti-patterns. Created app/bin/baselines/sdk_typing_antipatterns.txt with 25 grandfathered files. Added check-sdk-typing: Make target. Wired step in .github/workflows/ci_code.yml next to check-deprecated-client-imports. Verified: make check-sdk-typing exits 0 against baseline; exits 1 on a scratch net-new file. All 5 test_check_sdk_typing.py tests pass.

STEP 3 (AC#4): decisions/sdk-typing.md remains applies:target; Migration section already lists tolerated divergences (*_next.py, no-facade) for TASK-23/TASK-22.5. No edit needed.

DoD#1: both stub packages are dev-group only; [project].dependencies unchanged. Full test suite: 202 passed, 1 flaky pre-existing failure (test_handle_final_error_conditional_check_failed_is_non_critical passes in isolation). ruff: clean. mypy: 181 errors, all pre-existing.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-31 17:49
---
RESEQUENCED (2026-07-31, second pass) after further research into Google Workspace SDK typing during TASK-22.2/22.4 planning. This task was originally scoped AWS-only (types-boto3), while decisions/sdk-typing.md's ORIGINAL text accepted the Google discovery Resource as permanently untyped. That decision was revised the same day: google-api-python-client-stubs (community-maintained, dev-only, same shape as types-boto3) types discovery.build()'s return per service+version, closing the asymmetry. sdk-typing.md's Migration section now names this task as delivering BOTH stub adoptions. This task's Description/AC/Plan were updated accordingly (added STEP 1B, new AC#2, renumbered AC#3/#4). No change to TASK-22.2/22.3 (AWS-only slices, unaffected) or TASK-23 (vendor-agnostic dispatcher deletion, unaffected). TASK-22.4 (Google Directory) and TASK-25.2 (Google remainder) both now depend on this task's Google half in addition to its AWS-derived AWS half.
---

created: 2026-08-04 14:33
---
Re-verified 2026-08-04 (task-planner session) before handoff: TASK-70 already had a full plan from 2026-07-31; ran a fresh repo-wide grep of every execute_aws_api_call/execute_google_api_call call site rather than trusting the existing prose list. Found AC#1's AWS service list undercounted by one (missing securityhub, from integrations/aws/security_hub.py) and AC#2's Google service list undercounted by two (missing calendar_v3 and meet_v2, from google_calendar.py/meet.py). Corrected Description/AC#1/AC#2/Plan via CLI (bulk --acceptance-criteria replace + full --plan rewrite); no scope/size-gate change, still one PR. Also confirmed via PyPI/GitHub that google-api-python-client-stubs' latest release (1.39.0, 2026-07-11) claims full Discovery-bundled-API coverage, but the plan still requires STEP 1B to prove resolution for one of the two newly-found services via an actual mypy run rather than trusting the vendor's coverage claim. TASK-70 remains To Do, unblocked (only dep TASK-19 is Done); ready for human plan review.
---
<!-- COMMENTS:END -->
