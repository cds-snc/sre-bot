---
id: TASK-25.2.5.8
title: >-
  Extract shared freeze-baseline guard plumbing into app/bin; move sdk-typing,
  vendor-contract and runtime-imports guards onto it; standardize their test
  names
status: To Do
assignee: []
created_date: '2026-09-17 15:13'
updated_date: '2026-09-17 17:47'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.5.7
references:
  - app/bin/check_sdk_typing.py
  - app/bin/check_vendor_package_contract.py
  - app/bin/check_runtime_imports.py
  - app/tests/unit/bin
  - app/Makefile
  - .github/workflows/ci_code.yml
parent_task_id: TASK-25.2.5
priority: high
ordinal: 225000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Enabling slice 2 of 2 for TASK-25.2.5.5 (guard tooling), approved 2026-09-17 while planning it. Runs after TASK-25.2.5.7 so the retired guard is not refactored.

Redundancy found (2026-09-17): iter_python_files is copied in check_sdk_typing.py, check_vendor_package_contract.py and check_runtime_imports.py (and the guard .7 retires); load_baseline and the net-new/stale OK/INFO/FAIL report are copied in check_sdk_typing.py and check_vendor_package_contract.py. The copies differ: check_sdk_typing.py filters excluded directories on absolute path.parts (every file is skipped if the checkout path contains a directory named like .venv), check_vendor_package_contract.py correctly filters on parts relative to the scan root; only the vendor guard is typed.

Scope:
- One shared module under app/bin (name settled in the plan) with a typed file walker (excluded names matched on root-relative parts; accepts a file root, which check_runtime_imports needs), baseline loading (ignores blanks and # comments; missing file -> empty set) and the net-new/stale report returning the exit code. TASK-25.2.5.5's aws_platform seam guard is built on it.
- check_sdk_typing.py and check_vendor_package_contract.py use all three; check_runtime_imports.py uses the walker only (it has no baseline). Each script keeps its own detection rules and prints the same lines as today, apart from the relative-path filter fix.
- Import mechanics (verified): run as 'python bin/check_x.py' puts app/bin, not app/, on sys.path, so 'from bin.<helper> import ...' fails in script mode. The plan picks and verifies one mechanism, e.g. Makefile targets switch to 'uv run python -m bin.check_x', so every make target and CI step keeps working.
- Tests: tests/unit/bin/test_check_{sdk_typing,vendor_package_contract,runtime_imports}.py are renamed to test_bin_<guard>_check.py (human decision 2026-09-17: test_bin_<guard>_check.py) and repointed; the helper gets its own test_bin_<helper>_check-style file. Assertions stay behavioural.

Out of scope: changing any guard's detection rules or baseline contents; new guards; ADRs (no decision changes).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A single typed shared module in app/bin provides the file walker, baseline loading and the net-new/stale report; no guard script defines its own iter_python_files or load_baseline
- [ ] #2 make check-sdk-typing, make check-vendor-package-contract and make check-runtime-imports print the same OK/INFO lines as before the change (before/after output recorded in notes), and the CI steps calling them are unchanged or updated in the same PR
- [ ] #3 Excluded directories are matched on paths relative to the scan root, pinned by a unit test with an excluded-name directory above the root
- [ ] #4 The three guard test files are renamed to test_bin_<guard>_check.py and the helper has its own test file; failing-baseline, stale-only and walker cases are covered
- [ ] #5 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-09-17 on main @ 51509443, after TASK-25.2.5.7 merged)
- Guards in app/bin/: check_sdk_typing.py (101 LOC), check_vendor_package_contract.py (155), check_runtime_imports.py (193). bin/__init__.py exists, so bin is a package. dev-token.py and generate_client_usage_matrix.sh are unrelated and untouched.
- Duplication confirmed by reading all three:
  * iter_python_files x3. check_vendor_package_contract.py:54 filters on path.relative_to(root).parts (correct) and is typed -> Iterator[Path]. check_sdk_typing.py:40 filters on absolute path.parts and has no return annotation. check_runtime_imports.py:110 filters on absolute path.parts, is typed, and additionally returns root itself when root.is_file() (main.py is a shipped root).
  * EXCLUDED_DIR_NAMES x3. sdk and vendor: {__pycache__, .mypy_cache, .pytest_cache, .venv}. runtime: the same plus node_modules.
  * load_baseline x2 (check_sdk_typing.py:66, check_vendor_package_contract.py:112), byte-identical apart from the docstring.
  * The net-new/stale report x2 (check_sdk_typing.py:74-97, check_vendor_package_contract.py:121-153), same five print shapes with different wording. check_runtime_imports has no baseline and its own FAIL text; it is not a baseline report.
- Import mechanics, re-verified empirically (the task description's premise is WRONG and is corrected here): 'uv run python bin/check_sdk_typing.py' puts /workspace/app/bin on sys.path[0], yet 'import bin.check_sdk_typing' still succeeds, because .venv/lib/python3.14/site-packages/_editable_impl_sre_bot.pth puts /workspace/app on sys.path. So 'from bin.freeze_guard import ...' would work in script mode today. 'uv run python -m bin.check_x' puts /workspace/app on sys.path[0] directly. Both invocations were run for all three guards and printed byte-identical output with exit 0.
- Wiring: app/Makefile:97-104 defines the three targets, each 'uv run python bin/check_x.py'; Makefile:1 .PHONY already lists all three (synced by .7). .github/workflows/ci_code.yml:46-57 runs them as make targets from ./app. No other caller anywhere in the repo (rg over /workspace excluding backlog/, .git, .venv).
- Tests today: tests/unit/bin/test_check_sdk_typing.py (6 tests), test_check_vendor_package_contract.py (21), test_check_runtime_imports.py (11) = 38 passed. All import via 'from bin import check_x as checker' (works: pytest runs from app/). The vendor tests monkeypatch checker.APP_ROOT / INTEGRATIONS_ROOT / BASELINE_PATH onto tmp_path trees, so every module constant must stay a module-level name read at call time.
- Direct callers of the moved functions in tests: test_check_sdk_typing.py:41; test_check_vendor_package_contract.py:199, :202-213, :216-219, :239. Nothing outside tests/unit/bin and bin/ references them.
- test_check_sdk_typing.py:3 carries 'from __future__ import annotations', which CLAUDE.md's 3.14 baseline marks unnecessary and itself deprecated. The file is being renamed anyway, so it goes (fix-in-touched-file, kept to one line).
- ruff: line-length 130, E501 ignored, isort known-first-party includes "bin", so 'from bin.freeze_guard import ...' sorts into the first-party block. mypy checks bin/ (it excludes only ^tests/).
- Pre-edit gate reference: ruff clean; mypy 'Found 80 errors in 28 files (checked 353 source files)'; pytest tests/unit/bin -> 38 passed; make check-sdk-typing -> 'OK: no net-new SDK anti-patterns (3 baselined file(s) remain).'; make check-vendor-package-contract -> 'OK: no net-new vendor-package contract violations (21 baselined entry(ies) remain).'; make check-runtime-imports -> 'OK: every shipped import resolves to the standard library, first-party code, or a runtime dependency.'

HUMAN DECISIONS 2026-09-17
- D1 Module name: app/bin/freeze_guard.py. Its test file is tests/unit/bin/test_bin_freeze_guard_check.py.
- D2 Invocation: the three make recipes switch to 'uv run python -m bin.check_x', and the guards' Usage docstrings switch to 'python3 -m bin.check_x'. Chosen for robustness, not necessity: script mode works today only because the project is installed editable, and -m does not depend on that. Target names, CI step names and CI step bodies are unchanged.
- D3 Report granularity: the full net-new/stale report moves into freeze_guard.report(...), message-parameterized and returning the exit code, so each guard's main() shrinks to one call. TASK-25.2.5.5's seam guard consumes it directly rather than re-copying the logic (its plan's A1 contingency does not fire).
- D4 Excluded directories: one shared default constant, the union {__pycache__, .mypy_cache, .pytest_cache, .venv, node_modules}, overridable by parameter but overridden by nobody. Behaviour-identical today: no node_modules exists under integrations/ or any shipped root.
- D5 Test names: test_bin_sdk_typing_check.py, test_bin_vendor_package_contract_check.py, test_bin_runtime_imports_check.py (decided 2026-09-17), plus the new helper file from D1.

ORDERED STEPS (all commands from app/)
Step 0 - Preconditions. No edits.
  a. Confirm .7 is in the branch base: check_deprecated_infra_client_imports.py absent, Makefile has no check-deprecated-client-imports target.
  b. Record the pre-edit outputs listed under "Pre-edit gate reference" above, on this branch, as the before half of AC#2 and AC#5. Any drift from the numbers there is recorded and used as the reference instead.

Step 1 - Failing tests first (AC#1, AC#3, AC#4). Create tests/unit/bin/test_bin_freeze_guard_check.py against the not-yet-existing module (see TEST MATRIX). Run it; record the ModuleNotFoundError.

Step 2 - The shared module (AC#1, AC#3). Create app/bin/freeze_guard.py, fully typed, stdlib only.
  - Module docstring: what a freeze-baseline guard is, the three pieces it provides, which guards consume which (check_sdk_typing and check_vendor_package_contract use all three; check_runtime_imports uses the walker only because it deliberately has no baseline; TASK-25.2.5.5's check_aws_platform_seam.py uses all three), and "imported, never run".
  - EXCLUDED_DIR_NAMES: frozenset({"__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "node_modules"}) (D4).
  - iter_python_files(root: Path, excluded: Iterable[str] = EXCLUDED_DIR_NAMES) -> Iterator[Path]: if root.is_file(), yield root and return (check_runtime_imports needs this for main.py); else yield sorted(root.rglob("*.py")) skipping any path with an excluded name in path.relative_to(root).parts. The docstring states why the match is root-relative: an absolute-parts match empties the whole scan when the checkout sits under a directory named like .venv.
  - load_baseline(baseline_path: Path) -> set[str]: stripped non-blank lines that do not start with "#"; a missing file returns set(), which is what lets a new guard be run against no baseline to seed one.
  - report(*, current: set[str], baseline: set[str], baseline_path: Path, app_root: Path, stale_label: str, fail_label: str, remediation: str, ok_template: str) -> int: computes sorted(current - baseline) and sorted(baseline - current), then prints exactly today's shapes -
      "INFO: {stale_label}:" then "  - {entry}" per stale entry;
      "FAIL: {fail_label}:" then "  - {entry}" per net-new entry, then "" + f"Baseline: {baseline_path.relative_to(app_root.parent)}", then remediation, returning 1;
      otherwise f"OK: {ok_template.format(count=len(current))}" and 0.
    Keyword-only so call sites read as a spec. app_root is passed (not a pre-rendered string) so the vendor tests' monkeypatched APP_ROOT keeps producing a tmp-relative Baseline line.

Step 3 - check_sdk_typing.py (AC#1, AC#2). Delete EXCLUDED_DIR_NAMES, iter_python_files and load_baseline; add 'from bin.freeze_guard import iter_python_files, load_baseline, report'. Keep APP_ROOT, INTEGRATIONS_ROOT, BASELINE_PATH, _ANTIPATTERN_RE, contains_antipattern and find_current_violations (which now calls the shared walker). main() becomes a single report(...) call with:
    stale_label   "baseline entries with no remaining anti-patterns (safe to remove)"
    fail_label    "files contain SDK typing anti-patterns but are not in the baseline"
    remediation   "Baselines only ratchet down (decisions/sdk-typing.md coexistence rule); migrate the consumer off execute_*_api_call / __doc__ scraping instead of widening the baseline."
    ok_template   "no net-new SDK anti-patterns ({count} baselined file(s) remain)."
  Update the Usage docstring line to 'python3 -m bin.check_sdk_typing'. No other docstring text changes.

Step 4 - check_vendor_package_contract.py (AC#1, AC#2). Same deletions and the same import. Keep classify_module, references_operation_result, _app_relative, find_current_violations, find_warnings. main() keeps its WARN block verbatim (warnings are not part of the baseline report), then returns report(...) with:
    stale_label   "baseline entries with no remaining violation (safe to remove)"
    fail_label    "vendor-package contract violations not in the baseline"
    remediation   "Vendor packages export only client factories, classify_<vendor>_error and settings (decisions/outbound-clients.md); move the logic into an adapter or infrastructure capability instead of widening the baseline."
    ok_template   "no net-new vendor-package contract violations ({count} baselined entry(ies) remain)."
  Drop the now-unused 'from collections.abc import Iterator' if nothing else needs it. Usage docstring -> 'python3 -m bin.check_vendor_package_contract'.

Step 5 - check_runtime_imports.py (AC#1, AC#2). Delete EXCLUDED_DIR_NAMES and iter_python_files; add 'from bin.freeze_guard import iter_python_files'. Keep Iterator (iter_unguarded_imports still yields). main(), find_violations and every message are untouched - this guard has no baseline and no report to share. Usage docstring -> 'python3 -m bin.check_runtime_imports'.

Step 6 - Wiring (AC#2). app/Makefile:97-104: the three recipes become 'uv run python -m bin.check_sdk_typing', '... -m bin.check_vendor_package_contract', '... -m bin.check_runtime_imports'. Target names and .PHONY:1 are unchanged, so .github/workflows/ci_code.yml needs no edit and the existing test asserting "make check-runtime-imports" in the workflow keeps passing.

Step 7 - Test renames (AC#4). Plain mv, no git commands.
  a. test_check_sdk_typing.py -> test_bin_sdk_typing_check.py. Remove 'from __future__ import annotations' (grounding). Line 41 'checker.load_baseline()' -> 'freeze_guard.load_baseline(checker.BASELINE_PATH)', adding 'from bin import freeze_guard'. The module-exists test keeps find_spec("bin.check_sdk_typing"). 6 tests.
  b. test_check_vendor_package_contract.py -> test_bin_vendor_package_contract_check.py. The two tests that exercise load_baseline as such (test_load_baseline_ignores_blank_and_comment_lines, test_load_baseline_missing_file_returns_empty_set) move to the helper file, since the behaviour is now the helper's. The two remaining call sites (:199, :239) become 'freeze_guard.load_baseline(checker.BASELINE_PATH)'. test_find_current_violations_ignores_non_python_files_and_cache_directories stays: it is the guard-level proof that the shared walker is actually wired in. 19 tests.
  c. test_check_runtime_imports.py -> test_bin_runtime_imports_check.py. No body change; it touches none of the moved functions. 11 tests.
  d. No __init__.py change; tests/unit/bin/__init__.py already exists. Delete the stale tests/unit/bin/__pycache__ entries for the old names so a rename cannot be masked locally.

Step 8 - Green and gates (AC#1-#5). Record the command and its actual output in notes.
  uv run pytest tests/unit/bin -q   -> expect 48 passed (38 + ~12 helper tests - 2 relocated), and the three new file names in --collect-only
  uv run ruff check . ; uv run ruff format --check .
  uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'   -> expect the Step 0b count with no error in bin/
  uv run pytest tests --ignore=tests/smoke   -> only the 6 known TASK-90 order leaks (test_webhooks_aws_sns.py x3, infrastructure/directory/test_google.py x3)
  make check-sdk-typing ; make check-vendor-package-contract ; make check-runtime-imports -> each prints the Step 0b line byte-identically (AC#2); paste before and after side by side
  Negative probe, not committed: create integrations/_probe_tmp/mirror.py containing 'from infrastructure.operations.result import OperationResult' and confirm make check-vendor-package-contract exits 1 naming both rules, then delete the directory and confirm OK again. Record the output.
  uv run python bin/check_sdk_typing.py -> still works (proves the -m switch is a hardening, not a repair); recorded as a note, not an AC.

Step 9 - Backlog. Check ACs #1-#5 one by one as each is verified, write the evidence into the notes, and leave the task In Progress for a human. Add a note for TASK-25.2.5.5: the shared module is bin/freeze_guard.py with iter_python_files / load_baseline / report as specified in Step 2, and guards are invoked as 'uv run python -m bin.check_x'.

AC TRACEABILITY
- AC#1 <- Steps 2, 3, 4, 5; evidence: rg for 'def iter_python_files|def load_baseline' under bin/ hits only freeze_guard.py
- AC#2 <- Steps 6, 8 (before/after make output, unchanged ci_code.yml)
- AC#3 <- Steps 2, 8 (the walker's root-relative filter plus the helper test with an excluded-name directory above the root)
- AC#4 <- Steps 1, 7, 8 (the four file names in --collect-only and the pass count)
- AC#5 <- Step 8

TEST MATRIX (tests/unit/bin/test_bin_freeze_guard_check.py; tmp_path trees, no monkeypatching needed since every helper takes its paths as arguments)
Walker:
  1. a .py file directly under root is yielded; a .md file is not
  2. a file under root/__pycache__ is skipped, and under root/.venv, .mypy_cache, .pytest_cache and node_modules likewise
  3. AC#3 regression: root is tmp_path/".venv"/"project"/"integrations" and holds vendor/client.py -> client.py is yielded. The old absolute-parts filter yielded nothing here, which is the bug being fixed
  4. root is a file -> it is yielded and nothing else
  5. results are sorted
  6. an explicit excluded= argument replaces the default (a directory named in it is skipped, one not named in it is walked)
Baseline loading (two relocated from the vendor file, so their coverage is not lost):
  7. blank lines, whitespace-only lines and # comments are ignored; entries are stripped
  8. a missing baseline file returns an empty set
Report:
  9. current == baseline -> exit 0 and one "OK: " line with {count} filled from len(current)
  10. stale only (baseline - current non-empty) -> exit 0, "INFO: <stale_label>:" and a "  - " line per stale entry, no FAIL
  11. net-new only -> exit 1, "FAIL: <fail_label>:" with a "  - " line per entry, the "Baseline: " line rendered relative to app_root.parent, and the remediation string
  12. both stale and net-new -> exit 1 with the INFO block printed before the FAIL block
  13. entries are printed sorted, not in set order
Guard-level (already covered, kept as the proof the guards actually use the helper): the vendor file's cache-directory test and the sdk file's baseline test.
Not TDD'd, and why: the Makefile invocation switch and the Usage docstring edits are configuration; they are proved by the before/after make output in Step 8 and by test_bin_runtime_imports_check.py's existing Makefile/CI assertion.

ASSUMPTIONS AND DOUBTS
- A1 The task description's claim that 'from bin.<helper> import ...' fails in script mode is false (grounding, verified both ways). The -m switch is therefore a deliberate hardening (D2), not a required fix, and the plan keeps script mode working as a belt-and-braces check in Step 8.
- A2 Adding node_modules to the two integrations guards' exclusions changes nothing today: no node_modules directory exists under app/integrations/ or any shipped root. If one ever appeared it would be correct to skip it.
- A3 The root-relative filter fix cannot change output on this checkout (/workspace/app contains no excluded name), so AC#2's byte-identical requirement and AC#3's fix do not conflict. The fix is proved by the unit test, not by the make output.
- A4 report()'s ok_template is formatted with str.format, so a future template containing a literal brace would need doubling. Both current templates and .5's are brace-free; noted in the docstring.
- A5 mypy count drift: the Step 0b count is the reference, not 80.
- A6 The 6 known pytest failures in the single-process run are pre-existing TASK-90 leaks; they are called out, not fixed.
- A7 No ADR changes. .7 already generalized decisions/migration.md rule 3 to every baseline under app/bin/baselines/, and this task changes no rule, no detection and no baseline content.

BLAST RADIUS AND ROLLBACK
- Runtime: none. bin/ is not in the wheel packages (pyproject.toml), nothing in shipped code imports it, and check_runtime_imports does not scan it.
- CI: three steps keep the same names and the same 'make' bodies; only the recipes behind them change. The failure mode is a typo in a recipe, which turns the step red immediately and locally.
- Guard coverage: unchanged by construction - detection rules, baselines and messages are untouched, and the before/after make output in Step 8 is the proof.
- A single git revert restores all three guards, the Makefile recipes and the old test names together. No baseline, ADR or runtime file is touched, so a revert cannot trip another guard.
- Ordering: needs .7 merged (done, 51509443). TASK-25.2.5.5 consumes freeze_guard and the -m convention; its Step 0a reads this plan's D1-D3.

SIZE
Production/tooling (tests excluded): 5 files. Added: bin/freeze_guard.py (~95 LOC). Edited: check_sdk_typing.py (-35/+12), check_vendor_package_contract.py (-40/+14), check_runtime_imports.py (-14/+2), Makefile (3 recipe lines rewritten). Roughly +125 / -92. Tests: 3 renames with small edits, +1 file (~150 lines), net +10 tests. One subsystem (bin guard tooling), no behaviour change, comfortably inside the single-PR size gate.
<!-- SECTION:PLAN:END -->
