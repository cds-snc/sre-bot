---
id: TASK-25.2.5.8
title: >-
  Extract shared freeze-baseline guard plumbing into app/bin; move sdk-typing,
  vendor-contract and runtime-imports guards onto it; standardize their test
  names
status: To Do
assignee: []
created_date: '2026-09-17 15:13'
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
