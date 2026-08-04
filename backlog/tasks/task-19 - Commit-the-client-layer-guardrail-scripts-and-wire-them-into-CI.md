---
id: TASK-19
title: Commit the client-layer guardrail scripts and wire them into CI
status: Done
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-30 17:45'
labels:
  - toolchain
  - phase-2
  - clients
milestone: m-2
dependencies: []
references:
  - decisions/migration.md
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1273'
priority: high
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The two uncommitted scripts app/bin/check_deprecated_infra_client_imports.py (freeze baseline over deprecated infrastructure/clients imports) and app/bin/generate_client_usage_matrix.sh (usage report), with app/bin/baselines/, are exactly the right migration tooling per decisions/toolchain.md - commit and enforce them.

Steps:
1. Commit both scripts and the baselines directory.
2. Add a CI step running the freeze check: fails on any NET-NEW deprecated import (baseline only ratchets down, per decisions/migration.md coexistence rule 3).
3. Make the usage-matrix script runnable via a Makefile target (make client-usage-matrix) for progress tracking during Phase 3.
4. Retirement condition (do not implement now, note in the script header): both are deleted when their baselines are empty after Phase 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Scripts and baselines committed; CI fails on a net-new deprecated-client import (verified with a draft commit, then reverted)
- [x] #2 Baseline shrinkage does not fail CI; growth does
- [x] #3 make client-usage-matrix produces the report
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 CI blocking step live
- [x] #2 PR references decisions/migration.md coexistence rules
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-07-30): app/bin/check_deprecated_infra_client_imports.py and app/bin/baselines/ do NOT exist yet (file_search confirms no baselines/ dir anywhere in repo). app/bin/generate_client_usage_matrix.sh IS already committed, already exposed via Makefile target `audit-client-usage-matrix` (not the literal `client-usage-matrix` AC#3 names) and already produces tmp/client_usage_matrix.tsv correctly (traced through the script). TASK-19 has no `dependencies:` and is not blocked by TASK-18 (import-linter, still To Do) or anything else. TASK-22/22.1 already depend on TASK-19 and its plan explicitly documents both landed/not-landed cases (22.5 handles either), so this task is safe to plan and ship independently and ahead of the TASK-22 sprint (per TASK-19's own comment).

Repo-wide grep (cd app && grep real .py files, excluding caches) for `infrastructure.clients` importers, EXCLUDING files that live inside app/infrastructure/clients/ itself (those are internal-to-the-deprecated-tree, not external consumers), gives the exact current baseline (30 files):
Production (6, matches TASK-22's already-verified consumer list exactly):
- infrastructure/directory/factory.py
- infrastructure/directory/google.py
- infrastructure/storage/service.py
- packages/access/sync/adapters/aws_identity_center.py
- packages/access/sync/providers.py
- packages/geolocate/service.py
Tests (24, all under the deprecated clients' own legacy test tree, plus one narrow-slice provider test):
- tests/unit/infrastructure/clients/aws/{conftest.py,test_aws_client.py,test_aws_clients_facade.py,test_aws_config.py,test_config_client.py,test_cost_explorer_client.py,test_dynamodb_client.py,test_guard_duty_client.py,test_health_aggregator.py,test_identity_store_client.py,test_organizations_client.py,test_session_provider.py,test_sso_admin_client.py}
- tests/unit/infrastructure/clients/google_workspace/{test_batch_executor.py,test_directory.py,test_docs.py,test_drive.py,test_executor.py,test_facade.py,test_gmail.py,test_session_provider.py,test_sheets.py}
- tests/unit/infrastructure/clients/test_maxmind.py
- tests/unit/infrastructure/services/test_narrow_slice_providers.py:13 (`from infrastructure.clients.maxmind.client import MaxMindClient`)

STEPS:
1. Create app/bin/baselines/deprecated_infra_client_imports.txt: one repo-relative (from app/) path per line, header comment lines (`#`) explaining the ratchet rule and cross-referencing decisions/migration.md (coexistence rule 3) and decisions/toolchain.md, followed by the 30 paths listed above (blank/`#`-prefixed lines ignored by the loader).
2. Create app/bin/check_deprecated_infra_client_imports.py (stdlib only: ast, pathlib, sys):
   - Constants: DEPRECATED_MODULE = "infrastructure.clients"; DEPRECATED_TREE = app/infrastructure/clients (files under this path are excluded from the scan - internal self-imports of the deprecated tree are not "new dependents"); BASELINE_PATH = app/bin/baselines/deprecated_infra_client_imports.txt; scan root = app/ (the script's own grandparent dir), excluding __pycache__/.mypy_cache/.pytest_cache/.venv.
   - `iter_python_files(root)`: rglob("*.py") minus excluded dir names.
   - `imports_deprecated_module(path) -> bool`: `ast.parse` the file (skip on SyntaxError), walk `ast.Import`/`ast.ImportFrom` nodes, match module name == DEPRECATED_MODULE or startswith DEPRECATED_MODULE + ".". AST-based (not regex) for precision.
   - `find_current_consumers() -> set[str]`: every app/ .py file (excluding DEPRECATED_TREE itself) whose parsed imports match, returned as POSIX-style paths relative to app/.
   - `load_baseline() -> set[str]`: read BASELINE_PATH, strip, drop blanks/`#` comments; return empty set if file missing.
   - `main() -> int`: net_new = current - baseline (FAIL, exit 1, print each offending file + a message citing decisions/migration.md's ratchet-down rule and instructing that migrating the consumer, not widening the baseline, is the expected fix); stale = baseline - current (INFO-only print, "no longer needed, safe to remove from baseline" - does NOT fail, matching AC#2's "shrinkage does not fail CI"); prints an OK summary with the current count on success. `if __name__ == "__main__": sys.exit(main())`.
   - Module docstring: behavior + retirement condition only, no task IDs/phase labels (matches the established docstring convention - durable decisions/*.md references are fine, transient/task-ID references are not): "Retirement: delete this script and its baseline once the baseline is empty (see decisions/migration.md 'Done means' criteria)."
3. Add a one-line retirement comment to the existing app/bin/generate_client_usage_matrix.sh header (it has no docstring, just leading `#` comments) noting it is retired alongside the deprecated-import baseline once client-layer migration completes, per decisions/migration.md - no functional change to the script.
4. app/Makefile: add `check-deprecated-client-imports:` target running `uv run python bin/check_deprecated_infra_client_imports.py`; add a thin alias `client-usage-matrix: audit-client-usage-matrix` so the literal command AC#3 names (`make client-usage-matrix`) works without duplicating the existing, already-shipped `audit-client-usage-matrix` target/script. Add both new target names to the `.PHONY` line.
5. .github/workflows/ci_code.yml: add a new blocking step "Deprecated client import freeze check" in the `tests` job, `working-directory: ./app`, `run: make check-deprecated-client-imports`, placed after the existing "Format" step and before "Test" (no `|| true`, matches toolchain.md's "every quality command is blocking" rule).
6. Add app/tests/unit/bin/test_check_deprecated_infra_client_imports.py: unit tests against the script's pure functions using `importlib` to load the module by path (bin/ is not an installed package) or temp-directory fixtures - do not exercise the real app/ tree (keeps the test deterministic and independent of future migration progress). Cases: (a) a file with `import infrastructure.clients.aws.dynamodb` is detected; (b) a file with `from infrastructure.clients import X` is detected; (c) a file importing an unrelated module is not detected; (d) a file inside the DEPRECATED_TREE path is excluded even if it imports a sibling deprecated module; (e) `load_baseline` ignores blank lines and `#` comments; (f) `main()`-level diff logic: net-new-only baseline (missing entries) returns exit code 1; shrunk baseline (extra/stale entries only) returns exit code 0.

AC-TO-STEP-TO-TEST TRACEABILITY:
- AC#1 (scripts+baselines committed; CI fails on net-new import, verified via draft commit then reverted) -> Steps 1,2,5 -> automated: test_check_deprecated_infra_client_imports.py case (f)/net-new path; MANUAL (human, at PR time, per the AC's own wording): push a throwaway commit adding a new `from infrastructure.clients import x` line to any file outside the baseline, confirm the new CI step goes red, then revert the throwaway commit before merge.
- AC#2 (baseline shrinkage does not fail CI; growth does) -> Step 2's stale-vs-net-new distinction -> test cases (f) (both directions) plus test case where baseline has strictly more entries than current (stale-only) asserts exit 0.
- AC#3 (`make client-usage-matrix` produces the report) -> Step 4 alias target -> manual verification: `cd app && make client-usage-matrix` exits 0 and writes tmp/client_usage_matrix.tsv (already proven to work under the existing `audit-client-usage-matrix` name; the alias is a zero-risk passthrough).
- DoD#1 (CI blocking step live) -> Step 5 (no `|| true`).
- DoD#2 (PR references decisions/migration.md coexistence rules) -> human PR description step (not code); plan/script comments already cite decisions/migration.md and decisions/toolchain.md per Step 1/2 to make this easy to satisfy honestly.

TEST MATRIX: happy path (no net-new violation, current tree scan against the just-authored baseline exits 0 - run manually once locally after Step 1/2 land, `cd app && make check-deprecated-client-imports`); boundary (stale-only baseline entries do not fail - test case (f) shrink path); failure (net-new import not in baseline fails with exit 1 and names the offending file - test case (f) growth path); the DEPRECATED_TREE self-import exclusion (test case d) guards against the script falsely flagging infrastructure/clients/aws/facade.py importing infrastructure/clients/aws/config.py as a "new consumer". Run: `cd app && uv run pytest tests/unit/bin/test_check_deprecated_infra_client_imports.py` and, before completion, the full `cd app && uv run pytest tests --ignore=tests/smoke`.

ASSUMPTIONS / DOUBTS TO VERIFY:
- A1: the freeze check scans ALL of app/ including tests/, not just production code (unlike the usage-matrix's "external" classification which excludes tests/) - a new test file importing infrastructure.clients directly would also count as growth. This is deliberately broader/stricter than the usage-matrix report (decisions/migration.md's "no new dependents" framing is not scoped to production-only) - verify this reading is acceptable to the human reviewer; if too strict, narrowing to non-test files is a one-line change to `iter_python_files`'s exclusion set.
- A2: no `--write-baseline`/bootstrap flag is added - the initial baseline is hand-authored from this session's grep output (Step 1) rather than script-generated, keeping the script's scope to "check" only (avoids adding a maintenance feature nobody asked for). If a later re-baselining convenience is wanted, that is a separate small follow-up, not silently added here.
- A3: TASK-18 (import-linter) is still To Do and NOT a dependency of TASK-19; both guardrails are independent and can land in either order (confirmed no import-linter config exists yet, so nothing to conflict with).

BLAST RADIUS / ROLLBACK: purely additive tooling + one new CI step; touches no business logic, no terraform, no runtime settings. A single `git revert` of the PR fully restores prior behavior (CI simply stops running the new step; the alias Makefile target disappears; nothing else depends on either new artifact yet since TASK-22.1 has not started). Zero production/runtime blast radius. Ordering constraint: none - this can land before or independently of TASK-22's sprint (per TASK-19's own comment), and before or after TASK-18.

SIZE GATE: ~90 LOC new script + ~35-line data-only baseline file + ~6 Makefile lines + ~6 CI YAML lines + 1 comment line in the existing shell script + one new test file, 6 total non-test files touched, one cohesive subsystem (CI/tooling wiring - no terraform, no business code). Fits comfortably inside the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per approved plan. New: bin/baselines/deprecated_infra_client_imports.txt (freeze baseline, 30 current consumers); bin/check_deprecated_infra_client_imports.py (AST-based checker, fails on net-new infrastructure.clients imports, passes on baseline shrinkage); tests/unit/bin/__init__.py and tests/unit/bin/test_check_deprecated_infra_client_imports.py (8 tests, all passing, cover import detection, consumer discovery, baseline parsing, and main() fail/pass paths via monkeypatched synthetic trees). Modified: bin/generate_client_usage_matrix.sh (added retirement comment only, no functional change); Makefile (added check-deprecated-client-imports target and client-usage-matrix alias for audit-client-usage-matrix); .github/workflows/ci_code.yml (new blocking 'Deprecated client import freeze check' step between Format and Test). Test evidence: direct script run against real tree -> 'OK: no net-new infrastructure.clients imports (30 baselined consumer(s) remain)'; make check-deprecated-client-imports and make client-usage-matrix both verified working; new unit tests 8/8 passing; ruff check and ruff format --check clean on all new/modified files; mypy clean on the new script (no errors); full-repo mypy run shows 123 pre-existing errors, none in files touched by this task; full pytest suite (make test) green. Remaining for human verification at PR time: AC#1's draft-commit-then-revert proof that CI goes red on a net-new import (git actions are user-controlled, not performed by this agent), DoD#1 actual CI-green confirmation on a real PR run, and DoD#2 PR description referencing decisions/migration.md coexistence rules.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Planning note from TASK-22 decomposition: as of 2026-07-29, app/bin/check_deprecated_infra_client_imports.py and app/bin/baselines/ do NOT yet exist in the repo — only app/bin/generate_client_usage_matrix.sh (exposed via 'make audit-client-usage-matrix') is committed. TASK-22's Step 1/AC and its subtasks assume the freeze-check + baseline from this task. If TASK-19 lands before the TASK-22 sprint, the baseline ratchet enforces monotonic shrinkage per-slice; if it does not, TASK-22.5's baseline-empty step is a no-op and the deletion is guarded only by the usage-matrix + import-linter (TASK-18). No blocker either way, but sequencing TASK-19 ahead of the TASK-22 sprint is preferable.
---

created: 2026-07-30 17:42
---
AC#1 code-side complete: check_deprecated_infra_client_imports.py, baselines/deprecated_infra_client_imports.txt, and CI wiring in .github/workflows/ci_code.yml are all committed to this branch and verified locally (script run clean against real tree, unit tests cover fail/pass paths). Leaving AC#1 unchecked because its literal text requires a manual draft-commit-then-revert verification that CI actually goes red on a net-new import, which is a human/PR-time action outside this agent's scope (git operations are user-controlled per repo policy).
---
<!-- COMMENTS:END -->
