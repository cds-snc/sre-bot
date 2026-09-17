---
id: TASK-25.2.5.7
title: >-
  Retire the empty infrastructure.clients freeze guard: script, baseline, test,
  make target and CI step
status: Done
assignee: []
created_date: '2026-09-17 15:13'
updated_date: '2026-09-17 17:34'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - app/bin/check_deprecated_infra_client_imports.py
  - app/bin/baselines/deprecated_infra_client_imports.txt
  - app/tests/unit/bin/test_check_deprecated_infra_client_imports.py
  - app/Makefile
  - .github/workflows/ci_code.yml
  - decisions/toolchain.md
  - decisions/migration.md
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.5
priority: high
ordinal: 224000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Enabling slice 1 of 2 for TASK-25.2.5.5 (guard tooling), approved 2026-09-17 while planning it.

app/bin/check_deprecated_infra_client_imports.py guards a tree that no longer exists: TASK-22.5 deleted app/infrastructure/clients/ and emptied app/bin/baselines/deprecated_infra_client_imports.txt (make check-deprecated-client-imports prints 'OK: ... (0 baselined consumer(s) remain)'). The script's docstring and decisions/toolchain.md ('retired once their baselines empty') both say to delete it at this point; TASK-22.5 left the full retirement as an open question, never picked up. Any reintroduced import of infrastructure.clients already fails at import time in pytest/mypy, since the package is gone.

Delete: app/bin/check_deprecated_infra_client_imports.py, app/bin/baselines/deprecated_infra_client_imports.txt, app/tests/unit/bin/test_check_deprecated_infra_client_imports.py; the check-deprecated-client-imports target and its .PHONY entry in app/Makefile; the 'Deprecated client import freeze check' step in .github/workflows/ci_code.yml. The Makefile target and the CI step are removed in the same PR so CI never calls a missing target.

No ADR edit: decisions/toolchain.md already prescribes retirement. Out of scope: the client-usage-matrix report (bin/generate_client_usage_matrix.sh) and every other guard.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 check_deprecated_infra_client_imports.py, its baseline and its test no longer exist; app/Makefile has no check-deprecated-client-imports target or .PHONY entry; ci_code.yml has no step calling it
- [x] #2 rg over the repo (excluding backlog/) for check_deprecated_infra_client_imports|check-deprecated-client-imports|deprecated_infra_client_imports returns zero hits
- [x] #3 make check-sdk-typing, make check-vendor-package-contract and make check-runtime-imports still print OK; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded in notes
- [x] #4 ADR text no longer describes the retired guard (human decision 2026-09-17): decisions/migration.md coexistence rule 3 covers import-linter ignore lists and every freeze baseline under app/bin/baselines/, its Checks bullet describes freeze guards generally, and a dated change note records both; decisions/outbound-clients.md drops the closed 'seven baselined deprecated-client consumers' tolerance, with a dated entry in its Changes list
- [x] #5 app/Makefile .PHONY lists exactly the defined make targets: the retired target and the undefined test-coverage are removed, and the 8 missing targets (check-runtime-imports, debug, install-ci, lint-types, lock-check, test-coverage-all, test-coverage-integration, test-new) are added (pre-existing drift fixed on the touched line, human decision 2026-09-17)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-09-17 on feat/delete_aws_dynamoddb_integration @ 7c139145)
- The guard is dead. app/infrastructure/clients/ does not exist (TASK-22.5). app/bin/baselines/deprecated_infra_client_imports.txt holds only its 8-line comment header. `uv run python bin/check_deprecated_infra_client_imports.py` prints "OK: no net-new infrastructure.clients imports (0 baselined consumer(s) remain)." Its docstring says "delete this script and its baseline once the baseline is empty", and decisions/toolchain.md:24 says the same ("retired once their baselines empty"). TASK-22.5 emptied the baseline and explicitly left full retirement as an open follow-up.
- Every reference (rg over the repo, excluding backlog/, .git, .venv and __pycache__):
  - app/bin/check_deprecated_infra_client_imports.py (103 lines)
  - app/bin/baselines/deprecated_infra_client_imports.txt (header only)
  - app/tests/unit/bin/test_check_deprecated_infra_client_imports.py (94 lines, 8 tests, imports only the checker)
  - app/Makefile:1: ".PHONY: … client-usage-matrix check-deprecated-client-imports check-sdk-typing check-vendor-package-contract". The line has drifted from the defined targets (checked 2026-09-17 by parsing the Makefile). It is missing 8 targets (check-runtime-imports, debug, install-ci, lint-types, lock-check, test-coverage-all, test-coverage-integration, test-new) and lists test-coverage, which is not defined or referenced anywhere (rg over Makefile, .github, .claude, CLAUDE.md).
  - app/Makefile:97-99: the target, its recipe and the blank separator line.
  - .github/workflows/ci_code.yml:46-49: the step "Deprecated client import freeze check" (name, working-directory, run) and the blank separator line.
- ADR text that describes the retired guard (human decision 2026-09-17: fix in this task):
  - decisions/migration.md:20 rule 3: "**Baselines only ratchet down:** the deprecated-import allowlist and import-linter baselines never gain entries."
  - decisions/migration.md:45 Checks: "- Baselines monotonically shrink: the deprecated-import guardrail compares the tree against its baseline and fails on any net-new violation (run in CI once [toolchain.md](toolchain.md)'s ticket wires it)."
  - decisions/outbound-clients.md:62 Migration: "- the seven baselined deprecated-client consumers;". This tolerance was closed by TASK-22.5. The file records changes in a top "**Changes:**" bullet list (latest: 2026-09-11), while migration.md appends "**Change note (date, …):**" paragraphs at the end (latest: 2026-09-08).
- Left unchanged (human decision 2026-09-17): migration.md:35 "Done means: … the deprecated-client baseline empty" (a completion criterion that is already met) and toolchain.md:24 (the retirement rule this task carries out).
- Not in scope, and not references to the guard: bin/generate_client_usage_matrix.sh:47 (a report filter on the old path) and tests/unit/packages/geolocate/test_service_import_boundaries.py:15 (a geolocate import-boundary assertion).
- Remaining freeze guards and baselines after this task: check_sdk_typing.py (sdk_typing_antipatterns.txt) and check_vendor_package_contract.py (vendor_package_contract.txt). check_runtime_imports.py has no baseline. tests/unit/bin/__init__.py stays, because the other guard tests use the package.
- Gate baselines: mypy reports "Found 80 errors in 28 files (checked 354 source files)", none under bin/, so after deletion expect 80 errors in 28 files with 353 files checked. pytest: the last recorded run (TASK-25.2.5.6) was 6 failed, 3514 passed; expect 8 fewer passes. The 6 failures are the known TASK-90 order leaks.

HUMAN DECISIONS 2026-09-17
- D1 Retire the guard fully (script, baseline, test, make target, .PHONY entry, CI step) in one PR, so CI never calls a missing target.
- D2 ADRs: generalize migration.md rule 3 and its Checks bullet to every freeze baseline, remove the closed outbound-clients.md tolerance, and add a dated note in each file's own style. The rule 3 generalization was moved here from TASK-25.2.5.5, which no longer edits ADRs.
- D3 .PHONY is fully synced with the defined targets on the line being edited: add the 8 missing targets and drop the undefined test-coverage (widened from "check-runtime-imports only" after the full drift was found).
- D4 Show red/green with a temporary pytest module in the session scratchpad (the TASK-25.2.4.7 precedent). It is deleted afterwards and never committed.

ORDERED STEPS (commands from app/ unless noted)
Step 0 - Preconditions. No edits.
  a. Re-run the reference rg from the repo root: rg -n --hidden "check_deprecated_infra_client_imports|check-deprecated-client-imports|deprecated_infra_client_imports" --glob '!backlog/**' --glob '!.git/**' --glob '!**/.venv/**' --glob '!**/__pycache__/**' . Expect exactly the grounding list. Any other hit (a script, doc, skill or workflow) stops the task and goes back to the human.
  b. Confirm the baseline is still header-only and make check-deprecated-client-imports prints "0 baselined consumer(s)". If an entry has reappeared, stop.
  c. Record the pre-edit outputs of mypy, the pytest summary, make check-sdk-typing, make check-vendor-package-contract and make check-runtime-imports.

Step 1 - Red. Write <scratchpad>/test_retire_deprecated_guard_tmp.py (outside the repo), with paths resolved from /workspace:
  Removal asserts (all red before the edits):
  - the three files do not exist
  - importlib.util.find_spec("bin.check_deprecated_infra_client_imports") is None (run with app/ on sys.path)
  - the Makefile has no "check-deprecated-client-imports" text
  - ci_code.yml (yaml.safe_load) has no step whose run mentions it
  ADR asserts (red before the edits):
  - migration.md contains neither "deprecated-import allowlist" nor "deprecated-import guardrail compares"
  - migration.md contains "every freeze baseline under `app/bin/baselines/`" and a "**Change note (2026-09-17" paragraph
  - outbound-clients.md has no "seven baselined deprecated-client consumers" and has a "- 2026-09-17:" Changes entry
  .PHONY assert (red): the parsed .PHONY names equal the set of target names defined in the Makefile, excluding .PHONY itself. This is stronger than checking for one word.
  Retention asserts (green before and after): check_sdk_typing.py, check_vendor_package_contract.py, check_runtime_imports.py, their baselines and tests, tests/unit/bin/__init__.py, and the make targets and CI steps for check-sdk-typing, check-vendor-package-contract and check-runtime-imports all exist; migration.md still contains rule 3's "import-linter" wording and the :35 "Done means" line unchanged; toolchain.md:24 is unchanged.
  Run it with `uv run pytest <scratchpad file> -q` from app/ and record the pass/fail counts.

Step 2 - Delete the guard (AC#1). rm app/bin/check_deprecated_infra_client_imports.py, app/bin/baselines/deprecated_infra_client_imports.txt and app/tests/unit/bin/test_check_deprecated_infra_client_imports.py. Also remove the stale app/bin/__pycache__/check_deprecated_infra_client_imports.cpython-314.pyc locally (untracked; this keeps find_spec honest).

Step 3 - Makefile (AC#1, AC#5).
  - Line 1 becomes the defined targets in their existing order, with new names appended in file order: ".PHONY: dev dev-setup fmt install lint test test-unit test-integration test-legacy test-all fmt-ci lint-ci install-dev run test-coverage-unit backlog-board audit-client-usage-matrix client-usage-matrix check-sdk-typing check-vendor-package-contract check-runtime-imports debug install-ci lint-types lock-check test-coverage-integration test-coverage-all test-new". Step 0 re-derives the target list with the parse script (the regex ^([A-Za-z0-9_.-]+):(?!=)) in case the Makefile changed, and adjusts the line to match.
  - Delete lines 97-99 (target, recipe, trailing blank line), so client-usage-matrix is followed by one blank line and then check-sdk-typing.

Step 4 - CI (AC#1). In .github/workflows/ci_code.yml, delete lines 46-49 (the "Deprecated client import freeze check" step and its trailing blank line). "Format" is then followed directly by "SDK typing anti-pattern freeze check", with the existing 2-space step indentation and one blank line between steps.

Step 5 - ADRs (AC#4).
  a. decisions/migration.md:20 becomes: "3. **Baselines only ratchet down:** import-linter ignore lists and every freeze baseline under `app/bin/baselines/` never gain entries; a new baseline is seeded once, when its guard lands."
  b. decisions/migration.md:45 becomes: "- Baselines monotonically shrink: each freeze guard under `app/bin/` compares the tree against its baseline in CI and fails on any net-new entry; a guard is retired with its baseline once that baseline is empty ([toolchain.md](toolchain.md))."
  c. Append to the end of decisions/migration.md, after a blank line: "**Change note (2026-09-17, freeze baselines generalized):** rule 3 and the baseline check named the deprecated-import allowlist, which emptied under TASK-22.5 and whose guard TASK-25.2.5.7 retired. Both now cover every freeze baseline under `app/bin/baselines/`, so baselines added later (for example the `packages/aws_platform` seam baseline, TASK-25.2.5.5) are bound by the same ratchet without another amendment."
  d. decisions/outbound-clients.md: delete line 62 ("- the seven baselined deprecated-client consumers;"), and append under **Changes:** "- 2026-09-17: removed the closed 'seven baselined deprecated-client consumers' tolerance (TASK-22.5 migrated them; TASK-25.2.5.7 retired the guard)."
  Leave the frontmatter `date:` fields unchanged; existing change notes do not bump them.

Step 6 - Green and gates (AC#1-#5). Record the command and actual output in notes.
  uv run pytest <scratchpad file> -q -> all pass; then delete the scratchpad file
  uv run ruff check .
  uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> expect the Step 0c count, with one fewer file checked
  uv run pytest tests --ignore=tests/smoke -> only the 6 known order leaks (test_webhooks_aws_sns.py x3, infrastructure/directory/test_google.py x3), and 8 fewer passes than Step 0c
  make check-sdk-typing ; make check-vendor-package-contract ; make check-runtime-imports -> each prints the same OK line as in Step 0c
  make -n check-deprecated-client-imports -> "No rule to make target" (record it)
  Re-run the Step 0a rg -> zero hits (AC#2)
  uv run python -c "import yaml; yaml.safe_load(open('../.github/workflows/ci_code.yml'))" -> no error

Step 7 - Backlog. Check ACs #1-#5 one by one as each is verified, write the evidence into the notes, and leave the task In Progress for a human. TASK-25.2.5 ACs are untouched; this is an enabling slice that TASK-25.2.5.5 closes out.

AC TRACEABILITY
- AC#1 <- Steps 2, 3, 4; evidence: the scratchpad removal asserts, make -n output and the yaml load
- AC#2 <- Steps 0a, 6 (rg output)
- AC#3 <- Steps 0c, 6 (before/after gate outputs)
- AC#4 <- Step 5; evidence: the scratchpad ADR asserts and a git diff of both ADRs pasted in notes
- AC#5 <- Step 3; evidence: the scratchpad .PHONY-equals-targets assert

TEST MATRIX
No committed tests. The change removes a guard and its own tests and adds no runtime behaviour. The temporary scratchpad module (Step 1) provides:
- removal (happy path): files, module spec, make target, CI step
- boundaries/retention: the sibling guards, their baselines, tests, targets and CI steps, tests/unit/bin/__init__.py, migration.md:35 and toolchain.md:24 unchanged
- ADR wording: old phrases gone, new rule 3 and Checks wording present, dated notes present
- Makefile consistency: .PHONY names equal the defined targets
Regression guards in the real suite: the full pytest run shows no collection error from tests/unit/bin; mypy and ruff show no dangling import; the three remaining make checks give identical output; the CI YAML still parses.

ASSUMPTIONS AND DOUBTS
- A1 No other runner calls the target (pre-commit, devcontainer postCreate, scripts, skills). Verified by the Step 0a rg over hidden files, excluding only backlog/, .git, .venv and __pycache__.
- A2 CI step removal is safe to merge: ci_code.yml runs from the PR's own workflow file, so the PR that deletes the target also stops calling it. main has no branch-protection rule naming the step (human confirmation 2026-09-17; further checking is out of scope).
- A3 The rule 3 wording ("import-linter ignore lists") matches toolchain.md:24's ignore_imports mechanism. rg (2026-09-17) finds no import-linter config in pyproject.toml, Makefile, .github or an .importlinter file, and the rule describes the intended contract the same way the current text does.
- A4 The pytest pass count may have drifted since TASK-25.2.5.6. Step 0c records the actual count, and the expectation is relative (8 fewer).
- A6 The .PHONY sync changes no recipe. Only the targets make treats as phony change, and none of the added names matches a file or directory in app/ (verify: ls app/ for debug, test-new and the rest in Step 0).
- A5 The 6 known order-dependent failures are pre-existing (TASK-90) and are called out, not fixed.

BLAST RADIUS AND ROLLBACK
- Runtime: none. The script is not shipped (bin/ is not in the wheel packages) and nothing imports it.
- CI: one fewer step. The only failure mode is a leftover `make check-deprecated-client-imports` call elsewhere, which Step 0a rules out. The rg and the make -n check make it visible before merge.
- Guard coverage lost: nothing. Any import of infrastructure.clients already fails at import time in pytest and mypy, since the package no longer exists.
- A single git revert restores the script, baseline, test, target, CI step and ADR text together.
- Ordering: no prerequisites. TASK-25.2.5.8 depends on this task, and TASK-25.2.5.5 depends on .8.

SIZE
Production/tooling (tests excluded): 6 files. Deleted: the script (-103) and the baseline (-8). Edited: Makefile (the .PHONY line rewritten, -3), ci_code.yml (-4), migration.md (2 lines rewritten, +2), outbound-clients.md (-1/+1). Roughly -120 / +5. Tests: -1 file (94 lines). One subsystem (tooling) plus ADR bookkeeping, well within the size gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTATION (2026-09-17)
- Deleted app/bin/check_deprecated_infra_client_imports.py, app/bin/baselines/deprecated_infra_client_imports.txt and app/tests/unit/bin/test_check_deprecated_infra_client_imports.py (8 tests). Also removed their untracked __pycache__ .pyc files locally.
- app/Makefile: removed the check-deprecated-client-imports target (3 lines). The .PHONY line now lists exactly the defined targets: dropped the retired target and the undefined test-coverage, and added check-runtime-imports, debug, install-ci, lint-types, lock-check, test-coverage-integration, test-coverage-all and test-new. No recipe changed, and no file in app/ shares a name with the added targets.
- .github/workflows/ci_code.yml: removed the 'Deprecated client import freeze check' step. Format is now followed by 'SDK typing anti-pattern freeze check'.
- decisions/migration.md: rule 3 now reads 'import-linter ignore lists and every freeze baseline under app/bin/baselines/ never gain entries; a new baseline is seeded once, when its guard lands.' The Checks bullet describes freeze guards under app/bin/ generally, with retirement once a baseline is empty. A '**Change note (2026-09-17, freeze baselines generalized):**' was appended. Lines 35 (Done means) and toolchain.md:24 are unchanged, per the human decision.
- decisions/outbound-clients.md: removed the '- the seven baselined deprecated-client consumers;' tolerance and appended '- 2026-09-17: …' to its **Changes:** list. Plan correction: that list sits at the end of the file, not the top.

RED/GREEN (temporary pytest module in the session scratchpad, never in the repo, deleted after use)
- Before edits: 10 failed, 15 passed. The failures were file removal x3, module spec, Makefile target, CI step, migration wording x2, the outbound tolerance, and .PHONY == defined targets. The 15 passes were retention guards plus the .PHONY duplicate check.
- After edits, first run: 2 failed, 23 passed. Both failures were a defect in the temporary test, not the change: it asserted the old phrases appear nowhere in each ADR, but the new dated notes quote them on purpose. Narrowed to the rule 3 line, the Checks bullet and the tolerance list.
- After the fix: 25 passed.

EVIDENCE (from app/ unless noted)
- Precondition rg (repo root, --hidden, excluding backlog/.git/.venv/__pycache__) before edits: exactly the 3 files, Makefile:1, :97, :98 and ci_code.yml:48. make check-deprecated-client-imports -> OK: no net-new infrastructure.clients imports (0 baselined consumer(s) remain).
- Same rg after edits -> no hits (exit 1) (AC#2).
- make -n check-deprecated-client-imports -> make: *** No rule to make target 'check-deprecated-client-imports'.  Stop.
- uv run python -c "import yaml; yaml.safe_load(open('../.github/workflows/ci_code.yml'))" -> parses.
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> before: Found 80 errors in 28 files (checked 354 source files); after: Found 80 errors in 28 files (checked 353 source files). No new errors.
- uv run pytest tests --ignore=tests/smoke -> before: 6 failed, 3514 passed; after: 6 failed, 3506 passed (8 fewer, the deleted guard tests). The 6 are the known single-process order leaks (TASK-90), not caused here: test_webhooks_aws_sns.py x3 and infrastructure/directory/test_google.py x3.
- make check-sdk-typing -> OK: no net-new SDK anti-patterns (3 baselined file(s) remain). make check-vendor-package-contract -> OK: no net-new vendor-package contract violations (21 baselined entry(ies) remain). make check-runtime-imports -> OK: every shipped import resolves to the standard library, first-party code, or a runtime dependency. Identical before and after.

FOR THE HUMAN
- 7 files changed, 6 insertions and 216 deletions. No runtime, settings, env or terraform change.
- Next: TASK-25.2.5.8 (shared guard plumbing) is unblocked. The task is left In Progress.
<!-- SECTION:NOTES:END -->
