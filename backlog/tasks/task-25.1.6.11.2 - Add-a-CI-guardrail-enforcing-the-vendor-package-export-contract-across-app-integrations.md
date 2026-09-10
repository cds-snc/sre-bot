---
id: TASK-25.1.6.11.2
title: >-
  Add a CI guardrail enforcing the vendor-package export contract across
  app/integrations
status: To Do
assignee: []
created_date: '2026-09-10 17:26'
updated_date: '2026-09-10 17:50'
labels:
  - clients
  - phase-3
  - toolchain
milestone: m-3
dependencies:
  - TASK-25.1.6.11.1
  - TASK-25.1.7
references:
  - decisions/outbound-clients.md
  - decisions/layers.md
  - decisions/migration.md
  - app/bin/check_sdk_typing.py
  - app/tests/unit/bin/test_check_deprecated_infra_client_imports.py
  - .github/workflows/ci_code.yml
parent_task_id: TASK-25.1.6.11
priority: medium
ordinal: 184000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second (closing) slice of TASK-25.1.6.11. Adds new CI enforcement; reviewed for correctness. Modifies no vendor package.

WHY: decisions/outbound-clients.md Checks says 'Each vendor package exports exactly: factories, classify_<vendor>_error, settings', and decisions/layers.md says app/integrations/ holds construction plus classification and nothing else. Nothing enforces that. The Google Workspace mirror layer grew in exactly that gap and took the whole TASK-25.1.6 tree to remove. A convention that expensive to re-establish must be machine-enforced.

RULES (human-decided 2026-09-10):
- module rule: every .py file under app/integrations/<vendor>/ must be __init__.py, client.py or settings.py directly in the vendor directory. Any other module, and any file in a nested subpackage, is a violation. app/integrations/__init__.py is allowed. Vendor packages are the direct child directories of app/integrations/ EXCEPT the explicitly declared non-vendor directory utils/.
- non-vendor directory (human-decided 2026-09-10): utils/ is not a vendor package and must not be treated as one. Its modules are reported as a WARNING on stdout, never fail CI and are never baselined. The operation-result rule still applies to it.
- operation-result rule: no code reference to OperationResult anywhere under app/integrations/ (AST-based: import alias, Name or Attribute - not docstrings or comments). classify_<vendor>_error returns tuple[OperationStatus, error_code, retry_after], so the classification function never needs OperationResult; OperationStatus stays allowed.
- Scope: all vendors. Today's non-Google violations are frozen in a new ratchet-down baseline rather than fixed, mirroring bin/check_sdk_typing.py and decisions/migration.md coexistence rule 3. No other vendor is modified by this task.
- Home: a new script, bin/check_vendor_package_contract.py, with its own baseline. Deliberately NOT folded into check_sdk_typing.py: different concern, and that script's retirement condition is its own baseline emptying.

EXPECTED BASELINE (computed on main 2026-09-10, assuming TASK-25.1.6.11.1 and TASK-25.1.7 have landed; recompute at implementation time):
- module (23): aws/{config,cost_explorer,dynamodb,guard_duty,identity_store,lambdas,organizations,schemas,security_hub,shield,sqs,sso_admin}.py; openai/summarizer.py; slack/{blocks,bootstrap,channels,commands,formatter,help,models,parser,provider,users}.py
- operation-result (6): aws/shield.py, maxmind/client.py, openai/client.py, openai/summarizer.py, slack/formatter.py, slack/provider.py
- WARN only, not baselined: utils/api.py (its disposition is tracked separately)
- google_workspace: zero entries.
Before TASK-25.1.6.11.1 lands, google_workspace would contribute 5 module entries (google_calendar, google_meet, google_service, meet, schemas) and 1 operation-result entry (client.py); google_service.py remains until TASK-25.1.7. Hence the dependencies.

NOT IN SCOPE: fixing any baselined non-Google violation (owned by the TASK-25 tree, TASK-24 and the Slack runtime move); the disposition of integrations/utils/api.py; import-linter contracts (TASK-18); changes to classify_google_error.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 bin/check_vendor_package_contract.py exits non-zero when app/integrations/<vendor>/ contains a non-baselined module other than __init__.py, client.py or settings.py, including files in nested subpackages, proven by a deliberately failing fixture tree in its tests
- [ ] #2 The check exits non-zero when a non-baselined file under app/integrations/ references OperationResult in code, and passes when a file only uses OperationStatus or mentions OperationResult solely in a docstring or comment, each proven by fixture tests
- [ ] #3 Baseline entries are rule-qualified and only ratchet down: baselined violations pass, stale entries are reported without failing, and a baselined extra module that newly references OperationResult fails
- [ ] #4 The committed baseline contains zero app/integrations/google_workspace entries and the check passes against the real tree
- [ ] #5 make check-vendor-package-contract exists and .github/workflows/ci_code.yml runs it alongside the SDK typing freeze check
- [ ] #6 bin/baselines/sdk_typing_antipatterns.txt has zero google_workspace entries, and ruff, mypy, pytest tests --ignore=tests/smoke and bin/check_sdk_typing.py pass
- [ ] #7 Files under app/integrations/utils/ (not a vendor package) are reported as a non-failing warning by the module rule and are never baselined; the check still exits 0 while they exist
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read-verified on main 2026-09-10; re-grep line numbers before editing)
- app/bin/check_sdk_typing.py (101 LOC) is the shape to mirror: module constants APP_ROOT/INTEGRATIONS_ROOT/BASELINE_PATH, iter_python_files skipping cache dirs, load_baseline ignoring blank and # lines, and main() printing INFO for stale entries and FAIL for net-new, then returning the exit code. Wired at Makefile:100-101 (check-sdk-typing) and .github/workflows/ci_code.yml:50-52.
- app/tests/unit/bin/test_check_deprecated_infra_client_imports.py is the test pattern to mirror: tmp_path fixture trees built with a _write helper, monkeypatch.setattr(checker, "APP_ROOT" / "BASELINE_PATH", ...), capsys for output. (test_check_sdk_typing.py only asserts files exist and is not a model for behaviour tests.)
- Violations on main 2026-09-10 are listed in the description. After TASK-25.1.6.11.1 and TASK-25.1.7 land: 23 module + 6 operation-result entries, zero google_workspace, plus a non-failing WARN for utils/api.py.

STEP 1 - failing tests first: app/tests/unit/bin/test_check_vendor_package_contract.py
Named after its sibling checker tests in tests/unit/bin. Import the checker the same way the sibling test does. Build trees under tmp_path/"integrations" and monkeypatch APP_ROOT, INTEGRATIONS_ROOT and BASELINE_PATH. Docstrings describe behaviour only.
 T1 happy: integrations/__init__.py + vendor/{__init__,client,settings}.py -> no violations, main() returns 0.
 T2 deliberately failing fixture: vendor/mirror.py, empty baseline -> main() returns 1 and stdout names module:integrations/vendor/mirror.py.
 T3 nested subpackage: vendor/sub/__init__.py and vendor/sub/client.py -> both reported as module violations.
 T4 loose top-level module: integrations/helpers.py -> module violation; integrations/__init__.py alone -> clean.
 T5 non-vendor directory: utils/api.py and utils/__init__.py, empty baseline -> main() returns 0, stdout has a WARN line naming integrations/utils/api.py, and find_current_violations() does not contain it. Same tree plus utils/api.py referencing OperationResult -> main() returns 1 naming operation-result:integrations/utils/api.py.
 T6 OperationResult in code, one case each -> operation-result violation: `from infrastructure.operations.result import OperationResult`; `from infrastructure.operations import OperationResult as R`; `import infrastructure.operations as ops` + `ops.OperationResult`; a return annotation.
 T7 no false positives: only `OperationStatus` imported; OperationResult named only in a module docstring and in a # comment -> clean.
 T8 ratchet: violation listed in the baseline -> 0; baseline entry with no matching violation -> 0 and stdout INFO lists it as stale.
 T9 rule-qualified baseline: baseline holds module:integrations/vendor/extra.py, and extra.py also references OperationResult -> 1, naming operation-result:integrations/vendor/extra.py.
 T10 load_baseline ignores blank and comment lines; a missing baseline file yields an empty set.
 T11 boundaries: non-.py files (README.md) and __pycache__ contents are ignored.
 T12 real tree: main() with the real constants returns 0, and no baseline entry contains integrations/google_workspace/ or integrations/utils/.
 T13 wiring: Makefile defines check-vendor-package-contract: and ci_code.yml runs make check-vendor-package-contract.

STEP 2 - app/bin/check_vendor_package_contract.py (about 140 LOC, standalone; do not import from check_sdk_typing.py, since the two scripts retire independently)
- Constants: APP_ROOT, INTEGRATIONS_ROOT, BASELINE_PATH = bin/baselines/vendor_package_contract.txt, EXCLUDED_DIR_NAMES, ALLOWED_VENDOR_MODULES = frozenset({"__init__.py", "client.py", "settings.py"}), NON_VENDOR_DIRS = frozenset({"utils"}), RULE_MODULE = "module", RULE_OPERATION_RESULT = "operation-result".
- classify_module(path) -> "ok" | "violation" | "warn": take parts of path relative to INTEGRATIONS_ROOT. 1 part -> ok only for __init__.py. First part in NON_VENDOR_DIRS -> warn. 2 parts -> ok if the name is in ALLOWED_VENDOR_MODULES. Anything else -> violation.
- references_operation_result(path): ast.parse, then ast.walk matching ast.alias (name or asname), ast.Name.id or ast.Attribute.attr equal to "OperationResult". Docstrings are Constant nodes and comments never reach the AST, so neither matches. A SyntaxError propagates, so the check fails loudly rather than skipping a file.
- find_current_violations() -> set of "<rule>:<app-relative posix path>". find_warnings() -> sorted non-vendor module paths. main() prints WARN lines first (never affecting the exit code), then keeps check_sdk_typing.py's INFO and FAIL semantics and output format. The WARN text says integrations/ holds vendor packages only and that shared helpers belong with their consumer. The FAIL text points at decisions/outbound-clients.md: move the logic into an adapter or infrastructure capability instead of widening the baseline.
- Header docstring: purpose, both rules, the non-vendor warning, usage, and "delete this script and its baseline once the baseline is empty". No task ids in code comments.

STEP 3 - app/bin/baselines/vendor_package_contract.txt
Header comment in the style of sdk_typing_antipatterns.txt: only ratchets down, never add entries. Generate entries by running find_current_violations() on the real tree once TASK-25.1.6.11.1 and TASK-25.1.7 are merged, then diff the result against the 29 entries listed in the description. Any google_workspace or utils entry means a dependency has not landed or the non-vendor exclusion is broken: stop. Any other unexpected entry means new work landed since planning: list it in the PR description for the reviewer.

STEP 4 - wiring
app/Makefile: add check-vendor-package-contract to .PHONY and a target running `uv run python bin/check_vendor_package_contract.py`.
.github/workflows/ci_code.yml: add a "Vendor package contract freeze check" step (working-directory ./app, run make check-vendor-package-contract) directly after the SDK typing freeze check step.

STEP 5 - verification (from app/)
uv run pytest tests/unit/bin ; make check-vendor-package-contract (expect exit 0 with a WARN for integrations/utils/api.py while that file exists) ; uv run python bin/check_sdk_typing.py ; rg -n 'google_workspace|integrations/utils' bin/baselines/vendor_package_contract.txt (expect zero hits) ; rg -n google_workspace bin/baselines/sdk_typing_antipatterns.txt (expect zero hits) ; uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke. One-off manual sanity check, not committed: create integrations/google_workspace/mirror.py, confirm the make target exits 1 naming it, then delete it. T2 is the durable proof.

AC TRACEABILITY
AC#1 -> Steps 1-2; T2 (deliberately failing fixture), T3, T4, T11.
AC#2 -> Steps 1-2; T6, T7.
AC#3 -> Steps 1-2; T8, T9, T10.
AC#4 -> Step 3; T12.
AC#5 -> Step 4; T13, plus the CI run on the PR.
AC#6 -> Step 5 (the google_service.py baseline entry is pruned by TASK-25.1.7).
AC#7 -> Steps 1-2; T5, T12.

ASSUMPTIONS AND DOUBTS
(a) A file-name allowlist is an adequate proxy for "factories, classify, settings": client.py itself could still grow business logic. Accepted for now; review plus the per-vendor classification tests in outbound-clients.md Checks cover it. A symbol-level export check can come later if client.py regrowth is ever seen.
(b) NON_VENDOR_DIRS is an explicit one-entry allowlist, not a heuristic. A new non-vendor directory is a module-rule violation until someone deliberately adds it, which keeps "is this a vendor?" a reviewed decision.
(c) String-only references (getattr(module, "OperationResult"), string annotations) are not detected. Accepted: PEP 649 makes string annotations unnecessary, and ruff/mypy see real references.
(d) Concurrent merge risk: a PR adding a module under app/integrations/ that merges between baseline generation and this merge makes CI fail with a net-new entry. That is the guardrail working, but check open PRs touching app/integrations/ right before merging.
(e) TASK-25.1.6.14/.15 change only factory construction in client.py. A retries-disabled factory variant is compliant only if it stays in client.py; a new module would, by design, trip this check. Mention that in .15's planning if it has not started.
(f) ci_code.yml's trigger paths already cover app/bin/ changes, since the sibling freeze-check steps live in the same job. Verify the paths filter when adding the step.

BLAST RADIUS AND ROLLBACK
CI-only change; no runtime code touched. Worst case is a false positive blocking merges that touch app/integrations/; a single git revert removes the step, script and baseline. Ordering: must merge after TASK-25.1.6.11.1 and TASK-25.1.7 (enforced by dependencies), otherwise the baseline would have to carry google_workspace entries and AC#4 fails by design.

SIZE GATE
Production: 4 files, about +180 LOC (script about 140, baseline about 35, Makefile +3, ci_code.yml +4). Tests: 1 new file, about 220 LOC. Two subsystems (bin tooling, CI workflow), one change kind (new enforcement). Inside the gate.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-10 17:50
---
utils/api.py disposition (2026-09-10): retired by sibling TASK-25.1.6.11.3, which can run in parallel with this slice. Keep the NON_VENDOR_DIRS warning path as a generic safeguard; T5 builds its own fixture tree, so it does not depend on the real app/integrations/utils/ existing, and the real-tree run is correct whether or not .11.3 has landed.
---
<!-- COMMENTS:END -->
