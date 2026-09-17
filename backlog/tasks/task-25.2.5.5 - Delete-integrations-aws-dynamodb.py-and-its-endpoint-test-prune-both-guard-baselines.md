---
id: TASK-25.2.5.5
title: >-
  Delete integrations/aws/dynamodb.py and its endpoint test; prune both guard
  baselines
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
updated_date: '2026-09-17 16:06'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.5.2
  - TASK-25.2.5.3
  - TASK-25.2.5.6
  - TASK-25.2.5.8
references:
  - app/integrations/aws/dynamodb.py
  - app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/bin/baselines/vendor_package_contract.txt
  - decisions/migration.md
  - .github/workflows/ci_code.yml
  - app/Makefile
parent_task_id: TASK-25.2.5
priority: high
ordinal: 218000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (contract) of TASK-25.2.5, in the shape of TASK-25.2.4.7. Runs once .2 and .3 have merged and a re-grep finds no remaining reference.

- Delete app/integrations/aws/dynamodb.py (164 LOC) and app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py (the ENVIRONMENT-gate matrix for a gate that no longer exists). get_aws_client's AWS_ENDPOINT_URL_DYNAMODB gate is already covered by tests/unit/integrations/aws/test_aws_client_factory_config.py:89-102 (three tests), so no coverage moves.
- Prune app/bin/baselines/sdk_typing_antipatterns.txt:7 (integrations/aws/dynamodb.py) and vendor_package_contract.txt:8 (module:integrations/aws/dynamodb.py).
- Re-verify that no boto3.client/boto3.Session/boto3.resource construction exists in production code outside integrations/aws/client.py (true on 2026-09-15).
- Check TASK-25.2.5's ACs with a traceability note to the children, and leave its status for a human.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py no longer exist; rg over app/ (production, tests and mock.patch strings) for integrations.aws.dynamodb or 'from integrations.aws import dynamodb' returns zero hits
- [ ] #2 Neither guard baseline carries an integrations/aws/dynamodb.py entry and every other entry is unchanged; make check-sdk-typing and make check-vendor-package-contract print OK with no stale line naming it
- [ ] #3 rg for execute_aws_api_call|handle_aws_api_errors hits only integrations/aws/{client,sqs}.py, their legacy tests, bin/check_sdk_typing.py, the sdk_typing_antipatterns.txt header and decisions/sdk-typing.md, recorded in notes as owned by TASK-25.2.6; rg for boto3.(client|Session|resource) in production code hits only integrations/aws/client.py
- [ ] #4 TASK-25.2.5 ACs #1, #2, #3, #5 and #6 are checked with a traceability note to its children, AC #4 is left for TASK-25.2.5.4 with a note, and the parent's status is left for a human; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
- [ ] #5 A freeze-baseline guard bounds the packages/aws_platform transition seam: app/bin/check_aws_platform_seam.py, built on the shared guard module from TASK-25.2.5.8, plus app/bin/baselines/aws_platform_seam_consumers.txt. It scans every .py file under app/ except app/tests/, packages/aws_platform/ and the guard script itself, and fails on any unbaselined file that references the seam through absolute imports, 'from packages import aws_platform', relative imports resolved against the file's package, or non-docstring string constants naming packages.aws_platform (plus any pyproject.toml entry-point naming it); an unparsable file fails loudly; stale entries are reported without failing. The baseline is seeded once with exactly the production consumers present after .2, .3 and .6 (it only ratchets down), and the docstring names TASK-88 as retirement owner. Unit tests live in tests/unit/bin/test_bin_aws_platform_seam_check.py
- [ ] #6 The guard is wired as make check-aws-platform-seam (with its .PHONY entry) and as a CI step in .github/workflows/ci_code.yml next to the other freeze checks; it prints OK on the PR branch
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-09-17 on feat/delete_aws_dynamoddb_integration @ 7c139145)
- Legacy module: app/integrations/aws/dynamodb.py (164 LOC) builds its client at import time from infrastructure.configuration.integrations.aws and an ENVIRONMENT switch, and calls execute_aws_api_call. rg over app/ for integrations.aws.dynamodb|from integrations.aws import dynamodb|integrations/aws/dynamodb hits only tests/unit/integrations/aws/test_dynamodb_local_endpoint.py:9,:28 (41 lines, one parametrized test of that ENVIRONMENT switch), sdk_typing_antipatterns.txt:7 and vendor_package_contract.txt:8. No script, Makefile, CI, ADR or non-Python reference (repo rg, backlog/ excluded). tests/unit/bin/test_check_deprecated_infra_client_imports.py:13 matches only "infrastructure.clients.aws.dynamodb", and TASK-25.2.5.7 deletes that file.
- Coverage: the AWS_ENDPOINT_URL_DYNAMODB switch now lives in get_aws_client and is pinned by tests/unit/integrations/aws/test_aws_client_factory_config.py TestDynamoDbLocalEndpointGate (3 tests). No coverage moves.
- boto3.client/Session/resource in production code: only integrations/aws/client.py (:176, :182, :299, :303, :332).
- Dispatcher after deletion: execute_aws_api_call|handle_aws_api_errors remain in integrations/aws/{client,sqs}.py, tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py, bin/check_sdk_typing.py, the sdk_typing_antipatterns.txt header (:2) and decisions/sdk-typing.md, all owned by TASK-25.2.6.
- Seam consumers: 11 production files import packages.aws_platform: jobs/scheduled_tasks.py; modules/aws/{aws_account_health,identity_center,lambdas,ops_group_assignment,spending}.py; modules/incident/{db_operations,incident_folder}.py; modules/provisioning/{groups,users}.py; modules/slack/webhooks.py. This matches the 2026-09-16 comment. No production file uses importlib or __import__ on packages.aws_platform. pyproject.toml has no aws_platform entry-point. packages/aws_platform/** has no absolute self-imports.
- mypy baseline: Found 80 errors in 28 files (checked 354 source files). Two are in dynamodb.py (:102 no-any-return, :108 return-value), so 78 errors in 27 files are expected after deletion, unless .7 or .8 change the count.
- Guard execution: CI (.github/workflows/ci_code.yml:46-60) runs each freeze check as a make target from app/. bin/ is not a shipped wheel tree (pyproject.toml:196), so check_runtime_imports does not scan it. mypy does check bin/ (it excludes only ^tests/).
- TASK-25.2.5.4 has no dependency in either direction. It owns parent AC#4 and is still To Do.

HUMAN DECISIONS 2026-09-17
- D1 Split. Guard tooling work is done first in two enabling subtasks under TASK-25.2.5: .7 retires the empty infrastructure.clients guard, and .8 extracts the shared freeze-baseline module and renames the guard tests. This task depends on .8 (and .8 on .7). The old AC "in the shape of check_deprecated_infra_client_imports.py" is replaced, because that script is deleted by .7.
- D2 CI. Any guard added or modified is wired into CI in the same task, so the seam guard gets a ci_code.yml step (AC#6).
- D3 Scope. Scan every .py under app/, including bin/, jobs/, server/ and api/. Exclude app/tests/, packages/aws_platform/ (self-imports are not new dependents) and the guard script, whose own constants name the seam.
- D4 Thoroughness. Detect absolute imports, 'from packages import aws_platform', relative imports resolved to absolute, non-docstring string constants (importlib/patch/entry-point strings) and pyproject.toml entry-points. SyntaxError fails loudly. Rationale: a missed consumer is what breaks prod when TASK-88 dissolves the package.
- D5 Tests follow the standard: tests/unit/bin/test_bin_aws_platform_seam_check.py.
- D6 ADR. Superseded 2026-09-17 while planning TASK-25.2.5.7: the generalization of decisions/migration.md rule 3 (and its Checks bullet) moved to .7, the PR that retires the allowlist rule 3 named. This task makes no ADR edit; Step 0a confirms .7 landed that wording, which already covers the new seam baseline.
- D7 Close-out. Check parent ACs #1, #2, #3, #5 and #6. AC#4 waits for TASK-25.2.5.4.

ORDERED STEPS (all commands from app/)
Step 0 - Preconditions. No edits.
  a. Confirm .2, .3, .6, .7 and .8 are merged into the branch base. Read .8's notes for the shared module's name and API (the walker, load_baseline, the report function and its message parameters) and for the script execution mechanism (e.g. 'uv run python -m bin.check_x'). Steps 2 and 4 use exactly those.
  b. Re-run the grounding rg commands: the dynamodb references, the dispatcher, boto3 construction, and rg -l "packages\.aws_platform|from packages import aws_platform" over production dirs. A new dynamodb.py reference, or a seam consumer outside the 11 listed, stops the task and goes back to the human.
  c. Record the pre-edit mypy count.

Step 1 - Failing tests first (AC#5). Create tests/unit/bin/test_bin_aws_platform_seam_check.py, using .8's helper test style (tmp_path trees, monkeypatched module constants). See TEST MATRIX. Run it and record the failures (ModuleNotFoundError before Step 2).

Step 2 - Guard script (AC#5). Create app/bin/check_aws_platform_seam.py, typed, built on .8's shared module.
  - Constants: APP_ROOT; SEAM_MODULE = "packages.aws_platform"; SEAM_TREE = APP_ROOT/"packages"/"aws_platform"; TESTS_TREE = APP_ROOT/"tests"; SELF_PATH = Path(__file__).resolve(); BASELINE_PATH = bin/baselines/aws_platform_seam_consumers.txt; PYPROJECT_PATH.
  - _names_seam(dotted: str) -> bool: dotted == SEAM_MODULE or dotted.startswith(SEAM_MODULE + "."). The boundary check rejects packages.aws_platformer.
  - _package_parts(path) -> the file's app-relative package parts (its directory parts).
  - references_seam(path) -> bool. ast.parse, and a SyntaxError propagates. Collect docstring node ids (the first Expr/Constant str of the Module and of each FunctionDef, AsyncFunctionDef and ClassDef). Then walk:
      * Import: any alias.name passes _names_seam.
      * ImportFrom: resolve base = node.module if level == 0, else the package parts truncated by (level - 1) joined with node.module. Hit if _names_seam(base), or if _names_seam(f"{base}.{alias.name}") for any alias. The second form covers 'from packages import aws_platform' and 'from .. import aws_platform'.
      * Constant str (not a docstring) passing _names_seam.
  - pyproject_references_seam() -> bool: tomllib-load; any value in project.entry-points.* or project.scripts passes _names_seam, or starts with SEAM_MODULE + ":". A hit is reported under the entry "pyproject.toml".
  - find_current_consumers() -> set[str]: the shared walker over APP_ROOT, skipping TESTS_TREE, SEAM_TREE and SELF_PATH. App-relative posix paths, plus "pyproject.toml" when it references the seam.
  - main(): the shared report with this guard's lines: INFO "baseline entries no longer importing packages.aws_platform (safe to remove)"; FAIL "production files reference the packages.aws_platform transition seam but are not in the baseline", then "Baselines only ratchet down (decisions/migration.md coexistence rule 3); use the owning feature package or infrastructure capability instead of widening the seam (TASK-88)."; OK "no net-new packages.aws_platform consumers (N baselined consumer(s) remain)."
  - Module docstring: purpose, what is scanned and excluded, the detection forms, the ratchet rule, usage, and "Retirement: TASK-88 deletes this script, its baseline, the make target and the CI step when packages/aws_platform is dissolved."

Step 3 - Seed the baseline once (AC#5). Create app/bin/baselines/aws_platform_seam_consumers.txt with a header in the shape of the other baselines (enforced by, rule 3 ratchet, one app-relative path per line, stale reported and not failing, retired by TASK-88). Seed it by running the guard against an empty baseline and copying its FAIL list. It must equal the Step 0b rg list (11 sorted entries). Any difference is investigated, not pasted in.

Step 4 - Wiring (AC#6). In app/Makefile, add check-aws-platform-seam to .PHONY and add the target using .8's execution mechanism. In .github/workflows/ci_code.yml, add the step "packages/aws_platform seam freeze check" (working-directory ./app, run: make check-aws-platform-seam) directly after "Vendor package contract freeze check".

Step 5 - Contract deletion (AC#1, AC#2). rm app/integrations/aws/dynamodb.py and app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. Delete sdk_typing_antipatterns.txt line "integrations/aws/dynamodb.py" and vendor_package_contract.txt line "module:integrations/aws/dynamodb.py". Headers and all other entries stay byte-identical.

Step 6 - (removed: the ADR edit moved to TASK-25.2.5.7.)

Step 7 - Gates and evidence (AC#2-#6). Record the command and actual output in notes.
  uv run ruff check . ; uv run ruff format --check bin tests/unit/bin
  uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'  -> expect the Step 0c count minus 2, with none in the new script
  uv run pytest tests/unit/bin -> all pass; uv run pytest tests --ignore=tests/smoke -> only the 6 known order-dependent failures (test_webhooks_aws_sns.py x3, infrastructure/directory/test_google.py x3); use make test to confirm if needed
  make check-sdk-typing ; make check-vendor-package-contract ; make check-runtime-imports ; make check-aws-platform-seam -> each prints OK, with no INFO line naming dynamodb.py and no stale seam entries
  Negative probe (not committed): create a throwaway app/jobs/_seam_probe_tmp.py containing 'from packages import aws_platform', confirm make check-aws-platform-seam exits 1 and names it, then delete the file and confirm OK again. No existing file is edited. Record the output.
  The AC#1 and AC#3 rg commands, with output pasted.

Step 8 - Backlog close-out (AC#4). Check this task's ACs one by one as each is verified. On TASK-25.2.5, check ACs #1, #2, #3, #5 and #6, and append a traceability note: #1 <- .1; #2 <- .2, .3, .6; #3 <- .1-.3; #5 and #6 <- .5 (enabled by .7 and .8). AC#4 stays open for TASK-25.2.5.4. Leave both statuses for a human.

AC TRACEABILITY
- AC#1 <- Steps 0b, 5, 7 (rg output)
- AC#2 <- Steps 5, 7 (baseline diffs and the two make checks)
- AC#3 <- Steps 0b, 7 (two rg outputs, ownership noted)
- AC#4 <- Steps 7, 8
- AC#5 <- Steps 1, 2, 3, 7 (unit tests, seeded baseline, negative probe)
- AC#6 <- Steps 4, 7

TEST MATRIX (tests/unit/bin/test_bin_aws_platform_seam_check.py; tmp_path app trees with APP_ROOT, SEAM_TREE, TESTS_TREE, SELF_PATH, BASELINE_PATH and PYPROJECT_PATH monkeypatched)
Detection, happy path:
  1. 'import packages.aws_platform.adapters.dynamodb' -> True
  2. 'from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter' -> True
  3. 'from packages import aws_platform' -> True
  4. relative 'from ..aws_platform.adapters import config' in packages/foo/service.py -> True
  5. relative 'from .. import aws_platform' in packages/foo/service.py -> True
  6. 'importlib.import_module("packages.aws_platform.adapters.config")' -> True
Detection, boundaries:
  7. 'import packages.aws_platformer' and 'from packages import access' -> False
  8. a module, class or function docstring mentioning packages.aws_platform -> False
  9. relative 'from .aws_platform import x' in a file where it does not resolve to the seam (e.g. modules/foo/x.py) -> False
Failure:
  10. an unparsable file -> SyntaxError propagates
Scan scope:
  11. find_current_consumers excludes tests/, packages/aws_platform/ (self-import) and SELF_PATH, and includes bin/ and jobs/ consumers
  12. pyproject entry-point value "packages.aws_platform.x:y" -> "pyproject.toml" reported; a pyproject without entry-points -> not reported
main():
  13. an unbaselined consumer -> exit 1, path in stdout
  14. stale-only baseline -> exit 0, INFO line names the entry
  15. baseline equal to current -> exit 0, OK line with the count
Not TDD'd, and why: the deletion and baseline pruning change no live behaviour. They are guarded by the full pytest/mypy run (a leftover import fails at collection) and by the two make checks.

ASSUMPTIONS AND DOUBTS
- A1 The shared module API in .8 is not yet designed. Steps 1, 2 and 4 bind to whatever .8 ships (Step 0a). If .8 lands without a message-parameterized report function, this task calls its lower-level pieces and does not re-copy the report logic.
- A2 Docstring exclusion covers only real docstrings. A non-docstring string that merely mentions the seam (e.g. a log message starting with "packages.aws_platform") is flagged. That is accepted as a conservative false positive, fixed by rewording, and never by baselining.
- A3 Ordering: the 6 known pytest failures are pre-existing TASK-90 leaks (memory) and are called out, not fixed.
- A4 mypy count drift: the Step 0c count is the reference, not 80.
- A5 No production code reaches the seam via getattr on a 'packages' module object, or via exec. rg found none. This is out of the guard's reach and accepted.

BLAST RADIUS AND ROLLBACK
- Runtime: none. dynamodb.py has no live importer (Step 0b), and the guard, baseline, Makefile and CI changes are tooling. If a reference was missed, an ImportError at collection or type-check time fails CI before merge.
- CI: the new step fails the PR only on an unbaselined consumer. Because the baseline is seeded from the guard's own output on this branch, the PR is green by construction. Later PRs that add a consumer fail, which is the intent.
- A single git revert restores dynamodb.py, its test and both baseline lines, and removes the guard and CI step together. Baselines only shrink, so a revert cannot trip another guard.
- Ordering: depends on .2, .3, .6 (consumers migrated) and .8 (shared module), with .7 before .8. No env, settings or terraform prerequisite. TASK-88 inherits retirement of this guard (its AC#5).

SIZE
Production (tests excluded): 9 files. Added: check_aws_platform_seam.py (~90 LOC), aws_platform_seam_consumers.txt (~20 lines), plus Makefile +3, ci_code.yml +4. Deleted: dynamodb.py (-164) and 2 baseline lines. Roughly +117 / -166. Tests: +1 file (~180 lines) and -1 file (41 lines). One subsystem (tooling/guards) plus a deletion of dead legacy code, all within the size gate.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 13:48
---
2026-09-16 review: the seam guard lands here, in the contract slice, not in .1. The baseline must be seeded exactly once with the final consumer set, and .2 and .3 each add consumers - seeding in .1 would force the baseline to gain entries in two later PRs, which decisions/migration.md coexistence rule 3 forbids. Scope decision: the guard bounds all of packages/aws_platform, not just the DynamoDB adapter, because TASK-25.2 defines the whole package as a transition seam and TASK-88 dissolves it in one go; a DynamoDB-only guard would need a second one for the other adapters. Expected seeded baseline (re-grep at implementation): jobs/scheduled_tasks.py, modules/aws/aws_account_health.py, modules/aws/identity_center.py, modules/aws/lambdas.py, modules/aws/ops_group_assignment.py, modules/aws/spending.py, modules/provisioning/groups.py, modules/provisioning/users.py, plus modules/slack/webhooks.py, modules/incident/db_operations.py and modules/incident/incident_folder.py once .2 and .3 land. The scan covers production code only and skips app/tests/, so adding adapter tests stays friction-free; that differs from check_deprecated_infra_client_imports.py, which scans the whole tree, and the difference is deliberate - here the invariant is no net-new production consumer, not no net-new dependent.
---
<!-- COMMENTS:END -->
