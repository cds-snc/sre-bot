---
id: TASK-25.2.5.5
title: >-
  Delete integrations/aws/dynamodb.py and its endpoint test; prune both guard
  baselines; add the packages/aws_platform seam freeze guard
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-15 20:09'
updated_date: '2026-09-17 19:37'
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
- [x] #1 integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py no longer exist; rg over app/ (production, tests and mock.patch strings) for integrations.aws.dynamodb or 'from integrations.aws import dynamodb' returns zero hits outside tests/unit/bin/test_bin_freeze_guard_check.py, where the string is synthetic stale-baseline fixture data landed by TASK-25.2.5.8 and is not a reference to the module (narrowing approved by the human 2026-09-17)
- [x] #2 Neither guard baseline carries an integrations/aws/dynamodb.py entry and every other entry is unchanged; make check-sdk-typing and make check-vendor-package-contract print OK with no stale line naming it
- [x] #3 rg for execute_aws_api_call|handle_aws_api_errors hits only integrations/aws/{client,sqs}.py, their legacy tests, bin/check_sdk_typing.py, the sdk_typing_antipatterns.txt header and decisions/sdk-typing.md, recorded in notes as owned by TASK-25.2.6; rg for boto3.(client|Session|resource) in production code hits only integrations/aws/client.py
- [x] #4 TASK-25.2.5 ACs #1, #2, #3, #5 and #6 are checked with a traceability note to its children, AC #4 is left for TASK-25.2.5.4 with a note, and the parent's status is left for a human; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
- [x] #5 A freeze-baseline guard bounds the packages/aws_platform transition seam: app/bin/check_aws_platform_seam.py, built on app/bin/freeze_guard.py from TASK-25.2.5.8 (iter_python_files, load_baseline, report), plus app/bin/baselines/aws_platform_seam_consumers.txt. It scans every .py file under app/ except app/tests/, packages/aws_platform/ and the guard script itself, and fails on any unbaselined file that references the seam through absolute imports, 'from packages import aws_platform', relative imports resolved against the file's package, or non-docstring string constants naming packages.aws_platform (plus any pyproject.toml entry-point naming it); an unparsable file fails loudly; stale entries are reported without failing. The baseline is seeded once with exactly the 11 production consumers present after .2, .3 and .6 (it only ratchets down), and the docstring names TASK-88 as retirement owner and records the auto_discover_plugins blind spot. Unit tests live in tests/unit/bin/test_bin_aws_platform_seam_check.py
- [x] #6 The guard is wired as make check-aws-platform-seam (with its .PHONY entry, recipe 'uv run python -m bin.check_aws_platform_seam' per TASK-25.2.5.8) and as a CI step in .github/workflows/ci_code.yml next to the other freeze checks; it prints OK on the PR branch
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (re-verified 2026-09-17 on main @ 27fb2bda, after .2, .3, .6, .7 and .8 all merged)
- Legacy module: app/integrations/aws/dynamodb.py (164 LOC) builds client_config at import time from get_aws_settings/get_app_settings, hardcodes endpoint_url "http://dynamodb-local:8000" under ENVIRONMENT in (local, dev, ci), and decorates every operation with @handle_aws_api_errors over execute_aws_api_call. integrations/aws/__init__.py is empty, so deleting the module needs no __init__ edit.
- Live references to the module, rg over app/ (.venv excluded): tests/unit/integrations/aws/test_dynamodb_local_endpoint.py:9,:28 (41 lines, one parametrized 5-case test of that ENVIRONMENT switch), bin/baselines/sdk_typing_antipatterns.txt:7 and bin/baselines/vendor_package_contract.txt:8. No production importer, no script, Makefile, CI, ADR or non-Python reference.
- NEW since the previous plan: tests/unit/bin/test_bin_freeze_guard_check.py:127,:132 (landed by .8) uses the literal "integrations/aws/dynamodb.py" as the synthetic stale-baseline entry in test_stale_baseline_entries_are_reported_without_failing. It is tmp_path fixture data, touches no real path, and is deliberately left alone; AC#1 was narrowed to exclude that file (human decision D8 below).
- Coverage: the DynamoDB local-endpoint gate now lives in get_aws_client and is pinned by tests/unit/integrations/aws/test_aws_client_factory_config.py TestDynamoDbLocalEndpointGate (4 tests, :85-:110) over AWS_ENDPOINT_URL_DYNAMODB. The deleted test pins the retired ENVIRONMENT-switch mechanism, which no longer exists. No coverage moves.
- boto3.client/Session/resource in production code: only integrations/aws/client.py (:174, :176, :182, :297, :299, :303, :332).
- Dispatcher after deletion: execute_aws_api_call|handle_aws_api_errors remain in integrations/aws/{client,sqs}.py, tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py, bin/check_sdk_typing.py, sdk_typing_antipatterns.txt:2 (header) and decisions/sdk-typing.md. All owned by TASK-25.2.6.
- Seam consumers, unchanged at 11 production files: jobs/scheduled_tasks.py; modules/aws/{aws_account_health,identity_center,lambdas,ops_group_assignment,spending}.py; modules/incident/{db_operations,incident_folder}.py; modules/provisioning/{groups,users}.py; modules/slack/webhooks.py. packages/aws_platform/** has no absolute self-import. pyproject.toml has NO [project.entry-points] or [project.scripts] table at all, so pyproject_references_seam() is dead-but-cheap insurance against one being added.
- Plugin-discovery blind spot (new finding, not a blocker): server/lifespan.py:188 and infrastructure/plugins/manager.py:57 call auto_discover_plugins(pm, base_paths=["packages", "modules"]), which pkgutil.walk_packages the whole packages/ tree and importlib.import_module's each sub-package. packages.aws_platform is therefore imported at startup with no literal reference anywhere. No AST or string guard can see that, and it is not a net-new named dependent. The guard docstring records it so a future reader does not mistake the guard for proof that nothing imports the seam.
- Shared guard plumbing as built by .8: app/bin/freeze_guard.py -> iter_python_files(root: Path, excluded: Iterable[str] = EXCLUDED_DIR_NAMES) -> Iterator[Path] (yields a file root as itself; exclusions matched on parts relative to root); load_baseline(baseline_path: Path) -> set[str] (missing file -> empty set, which is how a first baseline is seeded); report(*, current, baseline, baseline_path, app_root, stale_label, fail_label, remediation, ok_template) -> int. report prints INFO stale, then FAIL + "Baseline: <path relative to app_root.parent>" + remediation, else "OK: <ok_template.format(count=len(current))>". ok_template must contain no brace but {count}. The message-parameterized report exists, so the previous plan's A1 contingency (re-copying the report) is dead and must not fire.
- Guard invocation as standardized by .8: Makefile:97-104 recipes are "uv run python -m bin.check_x"; .PHONY is Makefile:1. CI (.github/workflows/ci_code.yml:46-57) runs each as a make target with working-directory ./app. bin/ is not in the shipped wheel tree (pyproject.toml:196), so check_runtime_imports does not scan it; mypy does check bin/ (it excludes only ^tests/).
- Guard test naming as standardized by .8: tests/unit/bin/test_bin_{freeze_guard,runtime_imports,sdk_typing,vendor_package_contract}_check.py. This task adds test_bin_aws_platform_seam_check.py, which already matches.
- decisions/migration.md: the change note landed by .7 ("2026-09-17, freeze baselines generalized") already generalizes rule 3 and the Checks bullet to every baseline under app/bin/baselines/, and explicitly names "the packages/aws_platform seam baseline, TASK-25.2.5.5". No ADR edit in this task; Step 0a only confirms the wording is present.
- mypy pre-edit baseline: Found 80 errors in 28 files (checked 354 source files). Two of them are dynamodb.py:102 (no-any-return) and :108 (return-value). Expected after this task: 78 errors in 27 files, still 354 source files (-1 dynamodb.py, +1 check_aws_platform_seam.py, which must contribute zero errors).
- TASK-25.2.5.4 (parent AC#4) is still To Do with no dependency in either direction.

HUMAN DECISIONS
- D1 Split (2026-09-17). Guard tooling was done first in .7 (retire the empty infrastructure.clients guard) and .8 (extract the shared module, rename the guard tests). Both merged. The original AC wording "in the shape of check_deprecated_infra_client_imports.py" is dead, because .7 deleted that script.
- D2 CI. Any guard added or modified is wired into CI in the same task, so the seam guard gets a ci_code.yml step (AC#6).
- D3 Scope of the scan. Every .py under app/, including bin/, jobs/, server/ and api/. Excluded: app/tests/, packages/aws_platform/ (self-imports are not new dependents) and the guard script itself, whose own constants name the seam.
- D4 Thoroughness. Detect absolute imports, "from packages import aws_platform", relative imports resolved to absolute, non-docstring string constants (importlib/patch/entry-point strings) and pyproject.toml entry-points. SyntaxError fails loudly. Rationale: a missed consumer is what breaks prod when TASK-88 dissolves the package.
- D5 Tests follow .8's standard: tests/unit/bin/test_bin_aws_platform_seam_check.py.
- D6 ADR. Superseded 2026-09-17 while planning .7: the generalization of decisions/migration.md rule 3 moved to .7 and has landed. This task makes no ADR edit.
- D7 Close-out. Check parent ACs #1, #2, #3, #5 and #6. AC#4 waits for TASK-25.2.5.4. Parent status is a human's call.
- D8 NEW (2026-09-17, re-planning after .8 merged). AC#1 is narrowed rather than .8's just-merged test being edited: the "integrations/aws/dynamodb.py" string at test_bin_freeze_guard_check.py:127,:132 is synthetic baseline fixture data, not a reference to the module, and reads well as the entry this task prunes. That file is NOT touched by this task.
- D9 NEW (2026-09-17). The seam guard (AC#5, AC#6) stays in this task rather than moving to a new .9. The combined change passes the size gate (see below), decisions/migration.md already names this task as the seam baseline's owner, and parent AC#6 is assigned here. The task title was extended to name the seam guard so the scope is visible without opening the task.

SIZE GATE
Production files touched: 2 deleted (dynamodb.py 164 LOC, plus its 41-LOC test which is test code), 2 baselines pruned by one line each, 1 new guard script (~130 LOC), 1 new baseline (11 entries + header), Makefile (+3), ci_code.yml (+4). That is 7 production files and roughly +150 / -166 production LOC, plus 1 new test file. Under ~400 LOC and ~10 files. Two subsystems (app code + CI), which the gate allows. No mechanical refactor is mixed with a behaviour change: the refactor already shipped in .8. A single git revert restores both the module and the guard's absence. Gate passes; no decomposition.

ORDERED STEPS (all commands run from app/)
Step 0 - Preconditions. No edits.
  a. Confirm on the branch base: bin/freeze_guard.py exists with the three helpers; bin/check_deprecated_infra_client_imports.py does not; Makefile recipes use "python -m bin.check_x"; decisions/migration.md carries the 2026-09-17 generalization note.
  b. Re-run the four grounding greps (dynamodb references, dispatcher, boto3 construction, and rg -l "packages\\.aws_platform|from packages import aws_platform" over production dirs). A new dynamodb.py reference, or a seam consumer outside the 11 listed, stops the task and goes back to the human.
  c. Record the pre-edit mypy count and the pre-edit output of make check-sdk-typing and make check-vendor-package-contract.

Step 1 - Failing tests first (AC#5). Create tests/unit/bin/test_bin_aws_platform_seam_check.py in .8's helper-test style (tmp_path trees, monkeypatched guard constants, behavioural assertions, no real repository path). Run it and record the failures (ModuleNotFoundError before Step 2). See TEST MATRIX.

Step 2 - Guard script (AC#5). Create app/bin/check_aws_platform_seam.py, fully typed, stdlib only, importing iter_python_files, load_baseline and report from bin.freeze_guard.
  - Constants: APP_ROOT = Path(__file__).resolve().parent.parent; SEAM_MODULE = "packages.aws_platform"; SEAM_TREE = APP_ROOT/"packages"/"aws_platform"; TESTS_TREE = APP_ROOT/"tests"; SELF_PATH = Path(__file__).resolve(); BASELINE_PATH = Path(__file__).resolve().parent/"baselines"/"aws_platform_seam_consumers.txt"; PYPROJECT_PATH = APP_ROOT/"pyproject.toml".
  - _names_seam(dotted: str) -> bool: dotted == SEAM_MODULE or dotted.startswith(SEAM_MODULE + "."). The boundary check is what rejects packages.aws_platformer.
  - _package_parts(path: Path) -> tuple[str, ...]: the file's app-relative directory parts, used to resolve relative imports.
  - references_seam(path: Path) -> bool: ast.parse the source; a SyntaxError propagates (fails loudly). Collect the id()s of docstring nodes (the leading Expr/Constant str of Module, FunctionDef, AsyncFunctionDef and ClassDef), then walk:
      * ast.Import: any alias.name passes _names_seam.
      * ast.ImportFrom: base = node.module or "" when level == 0, else "." -joined (package parts truncated by level - 1) + node.module when present. Hit if _names_seam(base), or _names_seam(f"{base}.{alias.name}") for any alias. The second form is what catches "from packages import aws_platform" and "from .. import aws_platform".
      * ast.Constant with a str value whose id() is not a collected docstring id and which passes _names_seam.
  - pyproject_references_seam() -> bool: tomllib.load; any value under project.entry-points.* or project.scripts that passes _names_seam or starts with SEAM_MODULE + ":". Reported under the entry "pyproject.toml".
  - find_current_consumers() -> set[str]: iter_python_files(APP_ROOT), skipping any path under TESTS_TREE or SEAM_TREE and SELF_PATH itself; app-relative posix paths; plus "pyproject.toml" when pyproject_references_seam().
  - main() -> int: a single report(...) call with current=find_current_consumers(), baseline=load_baseline(BASELINE_PATH), baseline_path=BASELINE_PATH, app_root=APP_ROOT, stale_label="baseline entries no longer importing packages.aws_platform (safe to remove)", fail_label="production files reference the packages.aws_platform transition seam but are not in the baseline", remediation="Baselines only ratchet down (decisions/migration.md coexistence rule 3); use the owning feature package or infrastructure capability instead of widening the seam (TASK-88).", ok_template="no net-new packages.aws_platform consumers ({count} baselined consumer(s) remain)." Guard the entry point with if __name__ == "__main__": sys.exit(main()).
  - Module docstring: purpose; what is scanned and excluded; the five detection forms; the ratchet rule; "Usage: python3 -m bin.check_aws_platform_seam"; the auto_discover_plugins blind spot from GROUNDING; and "Retirement: TASK-88 deletes this script, its baseline, the make target and the CI step when packages/aws_platform is dissolved."

Step 3 - Seed the baseline once (AC#5). Create app/bin/baselines/aws_platform_seam_consumers.txt with a header in the shape of the other two baselines (what enforces it, the rule-3 ratchet, one app-relative path per line, stale entries reported and never failing, retired by TASK-88). Seed it by running the guard with no baseline file and copying the FAIL list verbatim. It must equal the Step 0b rg list: exactly the 11 sorted entries. Any difference is investigated, not pasted in.

Step 4 - Wiring (AC#6). app/Makefile: add check-aws-platform-seam to the .PHONY list on line 1 and add the target after check-runtime-imports with the recipe "uv run python -m bin.check_aws_platform_seam". .github/workflows/ci_code.yml: add the step "packages/aws_platform seam freeze check" (working-directory ./app, run: make check-aws-platform-seam) directly after "Vendor package contract freeze check".

Step 5 - Contract deletion (AC#1, AC#2). rm app/integrations/aws/dynamodb.py and app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. Delete the line "integrations/aws/dynamodb.py" from sdk_typing_antipatterns.txt and "module:integrations/aws/dynamodb.py" from vendor_package_contract.txt. Headers and every other entry stay byte-identical. Delete any stale __pycache__ entry for the removed module.

Step 6 - Gates and evidence (AC#2, #3, #4, #6). From app/: uv run ruff check . ; uv run ruff format --check . ; uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)' (expect 78 errors in 27 files, 354 source files; any other count is investigated before reporting); uv run pytest tests --ignore=tests/smoke (the 6 known TASK-90 single-process order leaks in test_webhooks_aws_sns.py and infrastructure/directory/test_google.py are called out, not fixed); make check-sdk-typing, make check-vendor-package-contract, make check-runtime-imports and make check-aws-platform-seam (all four must print OK, and the first two must show no stale line naming dynamodb.py). Record the command and its actual output in notes.

Step 7 - Close-out (AC#4). Check parent TASK-25.2.5 ACs #1, #2, #3, #5 and #6 with a per-AC traceability note naming the child that satisfied it (#1 -> .1; #2 -> .2/.3/.6; #3 -> .1-.3; #5 and #6 -> this task). Leave parent AC#4 unchecked with a note that TASK-25.2.5.4 owns it and is still To Do. Leave the parent's status for a human. Leave this task In Progress with notes.

TEST MATRIX (tests/unit/bin/test_bin_aws_platform_seam_check.py, all tmp_path, no real repo path)
- TestReferencesSeam (detection, AC#5):
  * "import packages.aws_platform" and "import packages.aws_platform.adapters.dynamodb as d" -> True (absolute import, both depths).
  * "from packages.aws_platform.adapters import dynamodb" -> True (ImportFrom base).
  * "from packages import aws_platform" -> True (the alias-joined form).
  * "from .. import aws_platform" inside packages/<pkg>/mod.py -> True (relative resolved against the file's package parts).
  * "from . import sibling" and "import packages.access" -> False (unrelated imports are not hits).
  * "import packages.aws_platformer" and "from packages import aws_platformer" -> False (the boundary check; this is the regression the startswith form would fail).
  * a module whose docstring mentions packages.aws_platform -> False; the same text as a module-level constant, an importlib.import_module argument and a mock.patch target -> True (docstring exclusion is by node identity, not by text).
  * a class docstring and a function docstring naming the seam -> False.
  * a file containing invalid Python -> SyntaxError propagates (pytest.raises), proving the guard fails loudly rather than skipping.
- TestFindCurrentConsumers (scan scope, AC#5):
  * a consumer under a scanned directory is reported as an app-relative posix path.
  * a consumer under tests/ is not reported (TESTS_TREE excluded).
  * a self-import inside packages/aws_platform/ is not reported (SEAM_TREE excluded).
  * the guard script's own path is not reported (SELF_PATH excluded).
  * a consumer under bin/ IS reported (D3: bin/ is in scope).
  * a non-.py file naming the seam is not reported (the walker only yields .py).
- TestPyprojectEntryPoints (AC#5):
  * an entry-point value "packages.aws_platform.plugin:register" -> "pyproject.toml" appears in the consumer set.
  * a [project.scripts] value naming the seam -> reported.
  * a pyproject.toml with no entry-point tables at all (today's real file) -> not reported.
- TestMain (report wiring, AC#5):
  * a tree matching its baseline exits 0 and prints exactly the OK line with the count filled in.
  * an unbaselined consumer exits 1, names that file, and prints the baseline path and the TASK-88 remediation.
  * a baselined consumer that no longer imports the seam exits 0 and prints the INFO stale line.
  These assert through report(), proving the shared module is wired in rather than re-implemented (AC#5's "built on freeze_guard").
No test is added for the deletion itself: AC#1-#3 are absence properties verified by rg and by the two guards printing OK, which is what Step 6 records.

ASSUMPTIONS AND DOUBTS
- A1 The message-parameterized report(...) from .8 covers this guard's four strings with no change to freeze_guard.py. Verified by reading bin/freeze_guard.py:67-108. If a wording need arises that report cannot express, the guard adapts its wording; freeze_guard.py is NOT modified in this task (that would re-open .8's scope).
- A2 The seam consumer list is exactly 11 at implementation time. Verified 2026-09-17, but .4 could land first and touch modules/incident or the idempotency store. Step 0b re-runs the grep and Step 3 refuses to paste a list it did not derive.
- A3 No non-import, non-string mechanism reaches the seam. Two known exceptions are documented rather than detected: the auto_discover_plugins walker (GROUNDING) and any future getattr-chain construction of the dotted name. The guard's purpose is to bound net-new NAMED dependents before TASK-88.
- A4 mypy lands at 78 errors in 27 files. If check_aws_platform_seam.py itself produces errors, they are fixed at the root (typed helpers, no ignore comments) before reporting.
- A5 tomllib is stdlib on 3.14 and needs no dependency. Verify with uv run python -c "import tomllib".

BLAST RADIUS AND ROLLBACK
- Runtime: none. dynamodb.py has no production importer (verified), and the guard runs only in CI and make. No route, settings, terraform or manifest change.
- CI: the new step can fail the pipeline if the baseline is wrong. Mitigated by Step 3 seeding from the guard's own output and Step 6 proving it prints OK on the branch.
- Ordering: no prerequisite outside the repo. .2, .3, .6, .7 and .8 are all merged.
- Rollback: a single git revert restores dynamodb.py, both baseline lines, and removes the guard, its baseline, the make target and the CI step together. Nothing depends on the guard existing.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTATION 2026-09-17, branch feat/delete_aws_dynamodb_integration. All six ACs verified individually. Task left In Progress for human review.

STEP 0 - Preconditions. bin/freeze_guard.py present; bin/check_deprecated_infra_client_imports.py gone (.7); all three Makefile recipes already 'uv run python -m bin.check_x' (.8); decisions/migration.md carries the 2026-09-17 "freeze baselines generalized" note, which already names this task's seam baseline, so no ADR edit was made. Re-greps matched the plan exactly: dynamodb referenced only by its own test plus the two baseline lines (and the .8 fixture string), and 11 seam consumers. Pre-edit mypy: Found 80 errors in 28 files (checked 354 source files).

STEP 1 - RED. Created tests/unit/bin/test_bin_aws_platform_seam_check.py (30 tests, 4 classes) against the not-yet-existing module. TestReferencesSeam (17) covers one detection form per test: absolute import at two depths, ImportFrom inside the seam, 'from packages import aws_platform', a relative 'from .. import aws_platform' resolved against the file's package, three unrelated-import negatives, three boundary negatives (packages.aws_platformer as import, from-import and string), three string-constant positives (module constant, importlib.import_module, mock.patch target), three docstring negatives (module, function, class) and a SyntaxError-propagates case. TestFindCurrentConsumers (6) pins the scan scope: app-relative posix output, bin/ in scope, tests/ excluded, the seam tree excluded, the guard script excluded, non-.py ignored. TestPyprojectEntryPoints (3) and TestMain (4) complete it. Every test points the checker's constants at a tmp_path tree, so none depends on the real repository.
Evidence: uv run pytest tests/unit/bin/test_bin_aws_platform_seam_check.py -q -> ImportError: cannot import name 'check_aws_platform_seam' from 'bin'; 1 error in 0.25s.

STEP 2 - GREEN. Created bin/check_aws_platform_seam.py (185 LOC, stdlib only, fully typed), importing iter_python_files, load_baseline and report from bin.freeze_guard; no plumbing re-copied. Detection is AST-based: _names_seam does the dotted-boundary check, _import_from_base resolves relative imports against the file's own package parts, _docstring_node_ids exempts docstrings by node identity rather than by text, and a SyntaxError propagates. pyproject_references_seam reads project.scripts and project.entry-points.* (today's pyproject declares neither, so it is insurance). -> 30 passed.

STEP 3 - Baseline seeded once from the guard's own output against an absent baseline (load_baseline returns an empty set precisely so a first baseline can be seeded this way). The 11 entries were diffed against the independent Step 0b rg list and are identical. Header follows the other two baselines and names TASK-88 as retirement owner.

STEP 4 - Wiring. Makefile: check-aws-platform-seam added to .PHONY:1 and a target with recipe 'uv run python -m bin.check_aws_platform_seam'. ci_code.yml: step "packages/aws_platform seam freeze check" (working-directory ./app) inserted directly after "Vendor package contract freeze check" and before "Runtime import check".

STEP 5 - Contract deletion. Removed integrations/aws/dynamodb.py (164 LOC) and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py, plus their stale __pycache__ entries. Pruned one line from each baseline (asserted single-occurrence before replacing); git diff --cached --stat shows exactly 1 deletion in each file and no other change.

EVIDENCE (all from app/)
- AC#1: integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py no longer exist. rg over app/ for the module hits only tests/unit/bin/test_bin_freeze_guard_check.py:127,:132, the synthetic stale-baseline fixture landed by .8 and explicitly excluded by this AC (human decision D8); that file was not touched.
- AC#2: sdk_typing_antipatterns.txt 3 -> 2 entries, vendor_package_contract.txt 21 -> 20. make check-sdk-typing -> "OK: no net-new SDK anti-patterns (2 baselined file(s) remain)."; make check-vendor-package-contract -> "OK: no net-new vendor-package contract violations (20 baselined entry(ies) remain)." Full output of both captured: no INFO stale line naming dynamodb.py, because the entry was removed in the same change as the file.
- AC#3: rg -l execute_aws_api_call|handle_aws_api_errors over the repo (backlog excluded) -> app/integrations/aws/{client,sqs}.py, app/tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py, app/bin/check_sdk_typing.py, app/bin/baselines/sdk_typing_antipatterns.txt (header) and decisions/sdk-typing.md. All owned by TASK-25.2.6. rg for boto3.(client|Session|resource) in production code -> only integrations/aws/client.py.
- AC#4: parent ACs #1, #2, #3, #5, #6 checked with a per-AC traceability comment on TASK-25.2.5; #4 left for TASK-25.2.5.4 with a note; parent status untouched. Gates below.
- AC#5: 30 tests in tests/unit/bin/test_bin_aws_platform_seam_check.py pass. Baseline holds the 11 production consumers, proven equal to an independent rg list. Guard built on freeze_guard (rg confirms it defines no walker, loader or report of its own).
- AC#6: make check-aws-platform-seam -> "OK: no net-new packages.aws_platform consumers (11 baselined consumer(s) remain)." make check-runtime-imports still OK. .PHONY updated; CI step added.

GATES
- uv run ruff check . -> All checks passed! (one SIM102 in the new script was fixed at source by flattening the Constant branch into the elif chain, not suppressed.)
- uv run ruff format --check . -> 736 files already formatted.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 78 errors in 27 files (checked 354 source files). Pre-edit was 80 in 28 across 354. Exactly the two dynamodb.py errors (:102 no-any-return, :108 return-value) are gone, the file count drops by one, and the source count is unchanged because the new guard replaces the deleted module. Zero errors in check_aws_platform_seam.py.
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3546 passed. The 6 are the known TASK-90 single-process order leaks (test_webhooks_aws_sns.py x3, unit/infrastructure/directory/test_google.py x3): they pass in isolation (111 passed) and make test, the project gate, is green at 2763 + 789 passed with zero failures. Pre-existing and unrelated; not fixed here.

DESIGN NOTE. The guard's docstring records a blind spot rather than pretending to cover it: server/lifespan.py:188 calls auto_discover_plugins(pm, base_paths=["packages", "modules"]), which walks the whole packages/ tree and imports every sub-package, so packages.aws_platform is imported at startup with no literal reference that any AST or string scan could see. The guard bounds net-new NAMED dependents, which is what TASK-88 must migrate.

FOR THE HUMAN
- 10 files: 2 added (bin/check_aws_platform_seam.py, bin/baselines/aws_platform_seam_consumers.txt), 1 added test file, 4 modified (Makefile, ci_code.yml, both baselines), 2 deleted (integrations/aws/dynamodb.py, tests/unit/integrations/aws/test_dynamodb_local_endpoint.py) and this task file. No ADR, runtime, settings or terraform change.
- No git command was run beyond read-only inspection. The test file and the test deletion are already in HEAD (commit 2a724ef4); the remaining eight files are staged and uncommitted.
- Task left In Progress. TASK-25.2.5's status is also left for a human, with only its AC#4 (TASK-25.2.5.4) outstanding.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 13:48
---
2026-09-16 review: the seam guard lands here, in the contract slice, not in .1. The baseline must be seeded exactly once with the final consumer set, and .2 and .3 each add consumers - seeding in .1 would force the baseline to gain entries in two later PRs, which decisions/migration.md coexistence rule 3 forbids. Scope decision: the guard bounds all of packages/aws_platform, not just the DynamoDB adapter, because TASK-25.2 defines the whole package as a transition seam and TASK-88 dissolves it in one go; a DynamoDB-only guard would need a second one for the other adapters. Expected seeded baseline (re-grep at implementation): jobs/scheduled_tasks.py, modules/aws/aws_account_health.py, modules/aws/identity_center.py, modules/aws/lambdas.py, modules/aws/ops_group_assignment.py, modules/aws/spending.py, modules/provisioning/groups.py, modules/provisioning/users.py, plus modules/slack/webhooks.py, modules/incident/db_operations.py and modules/incident/incident_folder.py once .2 and .3 land. The scan covers production code only and skips app/tests/, so adding adapter tests stays friction-free; that differs from check_deprecated_infra_client_imports.py, which scans the whole tree, and the difference is deliberate - here the invariant is no net-new production consumer, not no net-new dependent.
---

created: 2026-09-17 18:42
---
Re-planned 2026-09-17 on main @ 27fb2bda after .2, .3, .6, .7 and .8 merged. Scope adjustments: (1) AC#1 narrowed to exclude tests/unit/bin/test_bin_freeze_guard_check.py:127,:132, where .8 uses 'integrations/aws/dynamodb.py' as synthetic stale-baseline fixture data (D8, human-approved); that file is not touched. (2) AC#5/#6 now name the concrete .8 artefacts: bin/freeze_guard.py's iter_python_files/load_baseline/report and the 'uv run python -m bin.check_x' invocation, so the old 'read .8's notes for the API' contingency is gone. (3) Title extended to name the seam guard; the seam guard stays in this task (D9, human-approved, size gate passes at ~7 production files / ~+150/-166 LOC). (4) No ADR edit: the decisions/migration.md generalization landed in .7 and already names this task's seam baseline. (5) New finding recorded: auto_discover_plugins(base_paths=['packages','modules']) at server/lifespan.py:188 imports packages.aws_platform with no literal reference, so no AST/string guard can see it; documented in the guard docstring as a known blind spot rather than detected.
---
<!-- COMMENTS:END -->
