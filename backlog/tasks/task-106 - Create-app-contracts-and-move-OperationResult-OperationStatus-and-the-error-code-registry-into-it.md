---
id: TASK-106
title: >-
  Create app/contracts/ and move OperationResult, OperationStatus and the
  error-code registry into it
status: In Progress
assignee: []
created_date: '2026-09-24 19:57'
updated_date: '2026-09-28 16:56'
labels:
  - plugin-architecture
  - contracts
milestone: m-7
dependencies:
  - TASK-18
  - TASK-105.2
references:
  - decisions/plugin-architecture.md
  - decisions/operation-result.md
  - decisions/outbound-clients.md
priority: high
type: task
ordinal: 246000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: app/contracts/ is the public plugin API. It holds hookspecs, the core-service Protocols and shared types (OperationResult, OperationStatus, identifiers, an actor reference), contains no implementation and imports only the standard library, typing and pluggy markers. decisions/operation-result.md moves OperationResult there so every layer, integrations included, can import it.

This is the first contracts move, and it creates the package. It is mechanical: no behaviour change (the envelope fix lands first).

No shims. app/infrastructure/operations/ is deleted in the same change, with no re-export, and every importer is rewritten: packages, modules, integrations, infrastructure, server, jobs, api, tests, and unittest.mock patch-target strings. A per-layer split would need a temporary re-export, so a single codemod PR is the expected shape; the planner confirms it against the size gate. Record the file count and why a split would leave a shim.

The same PR applies the cascade: decisions/outbound-clients.md drops its tolerance for integrations importing infrastructure.operations, and the import-linter ignore entries that existed only for that import are removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 OperationResult, OperationStatus and the error-code registry live in app/contracts/; app/infrastructure/operations/ is deleted with no re-export or alias
- [x] #2 grep finds no infrastructure.operations import or patch-target string anywhere under app/
- [x] #3 The import-linter ignore entries that existed only for infrastructure.operations imports are removed, and the ruff isort known-first-party list includes contracts, features and capabilities
- [x] #4 decisions/outbound-clients.md and decisions/operation-result.md no longer list infrastructure/operations as a tolerated divergence
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #6 app/contracts/ exists and imports nothing from the app. This PR adds contracts to the import-linter root_packages and adds contract (c) (forbidden: contracts -> every other app root package) that TASK-18 deferred because app/contracts/ did not exist
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: pure mechanical codemod. Move app/infrastructure/operations/ (as left by TASK-105/105.1/105.2:
__init__.py, result.py, status.py, codes.py -- all stdlib-only, no app imports, confirmed 2026-09-28)
to app/contracts/operations/, delete the old location with no re-export, rewrite every importer,
apply the import-linter (c) contract that TASK-18 deferred, and remove the ignore entries that
existed only for infrastructure.operations. No behaviour change anywhere.

Ground truth (re-verified 2026-09-28 directly against the checked-out tree on
stack-a/task-105.2-error-code-registry, where TASK-18, TASK-105, TASK-105.1 and TASK-105.2 are all
landed -- this supersedes the prior pre-landing survey):
- infrastructure/operations/ has 4 files, 275 LOC (__init__.py 16, result.py 137, status.py 25,
  codes.py 97). classifiers.py is gone (deleted by TASK-105.1; confirmed zero `classifiers` hits
  anywhere under app/). result.py is frozen with no provider/operation/map/bind. codes.py defines
  `ErrorCode(StrEnum)` with 76 members. __init__.py exports exactly `ErrorCode`, `OperationResult`,
  `OperationStatus`. Confirmed all four files import nothing beyond stdlib (dataclasses, enum,
  typing) -- so AC #6 ("contracts imports nothing from the app") holds with zero extra changes
  needed in the moved files themselves.
- `rg -l 'infrastructure\.operations' --type py .` from app/ returns exactly 135 files today
  (confirmed by direct re-run, not an estimate). Re-run again immediately before writing the codemod
  script in case the branch has moved further before execution.
- Zero unittest.mock.patch string literals target `infrastructure.operations` anywhere (checked both
  `rg -n 'patch\(.*infrastructure'` and a literal-string grep) -- the task description's mention of
  "patch-target strings" is a category to check, not a finding; nothing to rewrite there.
- Zero bare `import infrastructure.operations`, zero `from infrastructure import OperationResult/
  OperationStatus` (the top-level infrastructure/__init__.py re-export at lines 12-14 still exists,
  still has no callers anywhere -- dead re-export, safe to delete outright).
- No Makefile, CI workflow, or other decisions/*.md file references infrastructure/operations or
  infrastructure.operations.
- Current app/pyproject.toml: `[tool.importlinter]` now exists (TASK-18 landed). `root_packages` =
  [server, packages, infrastructure, integrations, modules, api, jobs, models, utils] -- "contracts"
  not yet present. Contracts seeded: (a) layers, (b) no-host-imports, (d) integrations-leaf, (e)
  integrations-via-adapters, (f) feature-independence, (g) no-legacy-imports, (h) access-umbrella.
  Contract (c) does not exist yet -- confirmed, matches the task description's claim that TASK-18
  deferred it. `ignore_imports` entries containing the substring `infrastructure.operations` exist
  only in contracts (a), (b) and (d) (confirmed by direct grep of the landed pyproject.toml);
  contract (e) has none, so step 5's prune list below is scoped correctly as written. Ruff isort
  known-first-party (lines 58-71) unchanged = [api, bin, infrastructure, integrations, jobs, main,
  models, modules, packages, server, tests, utils]; hatch wheel `packages` (line 197) unchanged =
  [api, infrastructure, integrations, jobs, models, modules, packages, server, utils] (no
  "bin"/"tests"/"main" there).
- Other app/infrastructure/ content that decisions/plugin-architecture.md's contracts description
  ("hookspecs, core-service Protocols, identifiers, an actor reference") would eventually cover:
  infrastructure/plugins/specs.py (hookspecs) and the Protocol classes in infrastructure/{audit,
  idempotency,resilience/retry,storage,drive,directory,spreadsheets}/*.py. None of these are in scope
  here -- TASK-107/108/116/118 own them. No identifier type or actor-reference type exists anywhere
  yet. Reporting this per the planning brief's instruction to check, not widening this task.
- `ls app/packages` today: access, aws_platform, geolocate, incident, incident_draft,
  incident_summary, oncall_sync, rant, talent, user_rotations (context only, unchanged by this task).

Target layout: app/contracts/__init__.py (new, empty) + app/contracts/operations/{__init__,result,
status,codes}.py -- exact mirror of today's infrastructure/operations/ internal shape, only the root
segment changes. This matches TASK-26.1's app/contracts/slack/ and the other pending contracts.*
subpackages (108 storage, 116 current-user, 118 translator, 107 hookspecs) -- contracts/ is organized
one subpackage per concern, not flat.

Steps:

1. Content rewrite (mechanical, all 135 files, same edit): from app/,
   `rg -l 'infrastructure\.operations' --type py . | xargs sed -i -E 's/infrastructure\.operations/contracts.operations/g'`.
   This is a safe literal substring substitution: `infrastructure.operations` does not collide with
   any other identifier or path in the tree (verified: substring is distinctive), covers `from
   infrastructure.operations import X`, `from infrastructure.operations.result import X`, `from
   infrastructure.operations.status import X`, `from infrastructure.operations.codes import X`, and
   the package's own internal self-reference in __init__.py/result.py. No relative imports exist
   anywhere in this codebase (confirmed, zero `from \.` imports repo-wide), so the rewritten absolute
   `contracts.operations....` imports match house style exactly -- no follow-up cleanup needed.
   Re-run the file count immediately before this step; 135 is today's confirmed count, not a stale
   pre-landing estimate, but the branch may move again before execution.

2. Path relocation (mechanical):
   - `mkdir -p app/contracts && touch app/contracts/__init__.py` (empty, matches other root
     packages' __init__.py convention).
   - `git mv app/infrastructure/operations app/contracts/operations` (carries __init__.py, result.py,
     status.py and codes.py together -- codes.py is not a separate move, it travels with the rest of
     the directory).
   - `mkdir -p app/tests/unit/contracts && touch app/tests/unit/contracts/__init__.py`.
   - `git mv app/tests/unit/infrastructure/operations app/tests/unit/contracts/operations` (carries
     test_error_code_registry.py, added by TASK-105.2, and its __init__.py, into
     tests/unit/contracts/operations/ so the test tree mirrors app/contracts/operations/).
   - `git mv app/tests/unit/infrastructure/test_operations_result.py app/tests/unit/contracts/operations/test_operations_result.py`
     -- this file currently sits directly under tests/unit/infrastructure/ rather than in an
     operations/ subdir (pre-existing inconsistency); moving it into tests/unit/contracts/operations/
     aligns the test tree with the new production layout (app/contracts/operations/result.py). Bundled
     into this same mechanical move since the file's import already must change; not a separate edit.

3. app/tests/unit/contracts/operations/test_error_code_registry.py (added by TASK-105.2, moved by
   step 2): confirmed directly against today's file (`Path(__file__).resolve().parents[4]`,
   `EXCLUDED_DIRS = {"tests", ".venv", "__pycache__", ".mypy_cache"}`) that:
   - The `parents[4]` anchor is unaffected by the move: `tests/unit/infrastructure/operations/
     test_error_code_registry.py` and `tests/unit/contracts/operations/test_error_code_registry.py`
     have identical depth from app/ (file, operations/, {infrastructure|contracts}/, unit/, tests/ --
     five segments either way), so `parents[4]` still resolves to app/ after the move with no index
     change. Step 1's sed already rewrites this file's own `from infrastructure.operations import
     ErrorCode` to `from contracts.operations import ErrorCode`; no other line in the file changes.
   - `EXCLUDED_DIRS` contains `"tests"`, `".venv"`, `"__pycache__"` and `".mypy_cache"` -- it does not
     contain `"contracts"`, `"infrastructure"` or any other production root package name. The AST scan
     walks `APP_ROOT.rglob("*.py")` and excludes a file only if one of its path parts intersects that
     set, so app/contracts/ (and every other production root package) is scanned exactly like
     app/infrastructure/ was before the move -- no change to the walk logic is needed, and the
     registry's enforcement coverage does not shrink.

4. app/infrastructure/__init__.py: delete the "Base types" block (`from infrastructure.operations.
   result import OperationResult`, `from infrastructure.operations.status import OperationStatus`,
   both `__all__` entries, lines 12-14 and 17-19 confirmed against today's file) and the docstring's
   "Base types used across application (OperationResult, OperationStatus)" line -- confirmed zero
   callers of `from infrastructure import OperationResult`/`OperationStatus` anywhere, so this is a
   dead re-export removed outright, not a behaviour change.

5. app/pyproject.toml:
   - `[tool.ruff.lint.isort] known-first-party`: add "capabilities", "contracts", "features"
     (alphabetical, matches existing list's ordering), per AC #3's exact wording. features/
     capabilities don't exist as directories yet -- fine for ruff isort, which only uses the list as
     an import-grouping heuristic and does not require the package to be importable (unlike
     import-linter's root_packages).
   - `[tool.hatch.build.targets.wheel] packages`: add "contracts" only (the directory now exists).
     Do NOT add "features"/"capabilities" here -- hatch's packages list is used at build time and
     must reference real directories, same nonexistent-package constraint TASK-18 hit with
     import-linter's root_packages.
   - `[tool.importlinter] root_packages`: add "contracts" (now a real package, so it can finally be
     named directly rather than only via optional-layer syntax).
   - Add contract (c), immediately after contract (b) per the table's declared order: `type =
     "forbidden"`, name "contracts imports nothing else from the app", `source_modules =
     ["contracts"]`, `forbidden_modules` = every other root_package (server, packages, infrastructure,
     integrations, modules, api, jobs, models, utils), no `ignore_imports` (starts clean -- the moved
     files import only stdlib, confirmed above). This is the contract TASK-18's comment #1 and this
     task's AC #6 both point at; TASK-18 could not add it because contracts/ didn't exist and a
     forbidden contract has no optional-module syntax.
   - Contracts (a) layers, (b) no-host-imports and (d) integrations-leaf: confirmed today (not
     forward-looking) that their `ignore_imports` lists, seeded by the now-landed TASK-18, contain
     every `packages.*->infrastructure.operations*` and `integrations.*->infrastructure.operations*`
     edge (e.g. packages.access.*, packages.aws_platform.adapters.*, packages.geolocate.* on (b);
     integrations.aws.client, integrations.google_workspace.client, integrations.maxmind.client,
     integrations.openai.client/summarizer, integrations.slack.formatter/provider on (d)). Contract
     (e) integrations-via-adapters has zero `infrastructure.operations` entries today -- confirmed by
     direct grep -- so it needs no edit in this step. After step 1's rewrite, every one of the (a)/(b)/
     (d) edges above becomes `contracts.operations...`, which contract (c)'s `forbidden_modules` list
     does NOT include and which (b)/(d)'s `forbidden_modules` never listed either -- these edges become
     fully compliant, not merely re-ignored. Delete every `ignore_imports` line in contracts (a), (b)
     and (d) whose value contains the substring `infrastructure.operations` (mechanical grep-and-delete
     against the real pyproject.toml on this branch). `unmatched_ignore_imports_alerting = "error"`
     (already set) will fail the build if a stale entry is left behind, so a clean `lint-imports` run
     after this step is itself the verification. No other ignore_imports entries change (the AWS-STS,
     non-idempotent-write and other-infrastructure-import tolerances in outbound-clients.md are
     untouched -- only the operations-specific ones close here).

6. decisions/operation-result.md: remove "`OperationResult` and `OperationStatus` living in
   `app/infrastructure/operations/`" from the Tolerated-until-closed list in Migration (the only
   remaining open item there was this move); add a dated Changes entry, e.g. "2026-09-28: TASK-106
   moved OperationResult/OperationStatus/the error-code registry to app/contracts/operations/;
   app/infrastructure/operations/ deleted with no shim."

7. decisions/outbound-clients.md: in the Migration Tolerated-until-closed list, the bullet
   "`integrations/` importing `infrastructure.operations` instead of `contracts/`, plus 11 other
   `infrastructure` imports (...)" currently conflates two separate divergences. Reword it to drop
   only the `infrastructure.operations` clause -- e.g. "`integrations/` importing 11 `infrastructure`
   imports instead of `contracts/` (settings under `infrastructure.configuration`,
   `infrastructure.audit.models`, `infrastructure.i18n`, `infrastructure.slack.settings`); these
   become import-linter's ignore entries when TASK-18 lands" -- keeping the other 11 imports
   explicitly tolerated (unrelated to this task; TASK-24/26/etc. own them). Add a dated Changes entry
   noting the operations-import divergence closed by TASK-106.

AC traceability:
- AC #1 (OperationResult/OperationStatus/registry in app/contracts/, old location deleted, no shim)
  -> Steps 1-2.
- AC #2 (grep finds zero infrastructure.operations import/patch-target hits) -> Steps 1-2, verified by
  `rg -n 'infrastructure\.operations' app` returning zero (excluding none -- no patch-target strings
  exist to begin with, confirmed in survey).
- AC #3 (ignore entries removed; isort known-first-party has contracts/features/capabilities)
  -> Step 5.
- AC #4 (both decisions docs stop tolerating infrastructure/operations) -> Steps 6-7.
- AC #5 (gates) -> run ruff, mypy (scoped to touched files -- this PR touches ~140 files so "scoped"
  here is effectively the whole diff), `uv run lint-imports`, `pytest tests --ignore=tests/smoke`;
  report actual output at finalization.
- AC #6 (contracts/ exists, imports nothing from the app; root_packages + contract (c) added)
  -> Step 5's root_packages/contract (c) addition; verified by confirming the moved files' import
  lists contain only stdlib (dataclasses, enum, typing) plus their own contracts.operations.*
  siblings, and by `lint-imports` passing with contract (c) active.

Test matrix (codemod -- no new test files beyond what 105.2 already added and this task relocates):
- Happy path: full `pytest tests --ignore=tests/smoke` suite green after the move (every existing
  OperationResult/OperationStatus/ErrorCode test, including test_error_code_registry.py, continues to
  pass unchanged in content, only relocated and import-rewritten).
- Boundary/failure: `uv run lint-imports` fails if a stale ignore_imports entry is left unmatched, or
  if contract (c) is violated (deliberately verify once: add a throwaway `import server` line to
  contracts/operations/result.py, confirm lint-imports fails, then revert before committing -- same
  pattern TASK-18 used for its own contracts).
- Regression guard: `rg -n 'infrastructure\.operations' app` returns zero after the move; `rg -n
  'infrastructure\.operations'` also checked against non-.py files (Makefile, .github/workflows/,
  decisions/*.md) returns zero.

Assumptions and doubts:
- TASK-18, TASK-105, TASK-105.1 and TASK-105.2 are confirmed landed on the current tree (this plan's
  Ground Truth section re-verified their shape directly: frozen dataclass, provider/operation and
  classifiers.py gone, codes.py present with 76 ErrorCode members, import-linter contracts a/b/d/e/f/
  g/h seeded, contract (c) absent). If the branch this executes against has diverged further by then,
  re-run the Ground Truth greps against the actual tree before starting -- especially the exact
  ignore_imports contents for step 5, which this plan deliberately does not hand-transcribe in full.
- Assumes no dynamic/string-based plugin lookup resolves `infrastructure.operations` by dotted-path
  string (e.g. `importlib.import_module("infrastructure.operations...")`) anywhere -- grepped for
  quoted string literals containing "infrastructure.operations" repo-wide (excluding .venv) and found
  none; re-grep at execution time since a stray one would silently break at runtime rather than at
  import time.
- Assumes moving app/tests/unit/infrastructure/test_operations_result.py into
  app/tests/unit/contracts/operations/ (step 2) is the right call rather than leaving it flat under
  tests/unit/contracts/ -- flagged as a placement judgment call bundled into an otherwise pure move;
  reviewer may prefer leaving it flat to minimize path churn, in which case skip that one `git mv` and
  target `app/tests/unit/contracts/test_operations_result.py` instead.

Blast radius and rollback:
- Every production edit in this PR is either (a) a byte-identical import-path substitution across
  135 files, (b) a directory relocation of 4 files whose content is otherwise untouched, or (c) a
  config/decisions-doc edit with no runtime effect. No logic changes anywhere. A single `git revert`
  of the PR fully restores prior behaviour and prior import paths.
- Size-gate note (per implementation-planning skill, explicit deviation record): this PR touches 135
  files with the identical one-line substitution, plus app/contracts/{__init__,operations/*}.py
  (moved, not authored), plus the following genuinely non-uniform edits: infrastructure/__init__.py
  (dead re-export removal), pyproject.toml (isort list, hatch wheel packages, import-linter
  root_packages + new contract (c) + ignore-list pruning across contracts a/b/d), and two decisions
  docs. This exceeds the ~400 LOC / ~10 file guideline by file count alone, but per doc-2 and this
  task's own description a single codemod PR is the expected shape here -- splitting by layer would
  require a temporary re-export shim, which the task explicitly forbids, and splitting by file group
  would leave every remaining group's imports broken (once OperationResult leaves
  infrastructure.operations, every un-migrated importer fails at import time; there is no partial-migration
  state that keeps main green). Kept as one PR, matching TASK-105.1's already-accepted precedent for
  the same reasoning. The non-uniform edits above are listed in full, not buried in the mechanical
  count.
- Ordering: must land after TASK-18/105/105.1/105.2 (already declared); TASK-26.1 and TASK-107 (its
  declared dependents) assume app/contracts/ exists with this operations/ subpackage shape and that
  contracts/ takes one-subpackage-per-concern (slack/, hookspecs, etc.) -- flagging this as confirmed
  compatible with TASK-26.1's own title ("app/contracts/slack/"), not a new finding requiring their
  plans to change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented on stack-a/task-106-contracts (Stack A layer 6), per the approved plan.

- Moved app/infrastructure/operations/{__init__,result,status,codes}.py to app/contracts/operations/ (new empty app/contracts/__init__.py); old directory deleted, no re-export. Files moved with plain mv (git writes are the human's); git detects the renames on add.
- Rewrote infrastructure.operations -> contracts.operations in 137 .py files (135 in the plan; TASK-105.3 added two test imports). Then ruff --select I001 --fix re-sorted 41 import blocks, because contracts sorts before infrastructure (the plan expected no follow-up).
- Deleted the dead OperationResult/OperationStatus re-export from app/infrastructure/__init__.py.
- Tests: tests/unit/infrastructure/operations/test_error_code_registry.py and tests/unit/infrastructure/test_operations_result.py moved to tests/unit/contracts/operations/ (human decision), with __init__.py files for tests/unit/contracts/ and tests/unit/contracts/operations/ matching sibling test packages. codes.py docstring now points to the new test path.
- pyproject.toml: isort known-first-party += capabilities, contracts, features; hatch wheel packages += contracts; import-linter root_packages += contracts; layers contract uses contracts (not the optional (contracts)); new contract (c) id contracts-leaf forbids contracts -> every other root package; removed all 45 ignore_imports entries naming infrastructure.operations (contracts a, b, d). Negative check: a throwaway 'import utils' in contracts/operations/status.py broke (c), then was removed.
- decisions: operation-result.md Migration now lists no open divergence; outbound-clients.md drops the infrastructure.operations clause and the stale 'when TASK-18 lands' wording; plugin-architecture.md (not in the plan, but it also named the old location) now names contracts.operations as the shared kernel and drops the tolerated bullet. Dated Changes entries in all three.
- Finding, not fixed: packages/geolocate/platforms/slack.py:15 and packages/access/sync/interactions/slack.py:33 import SlackPlatformProvider under TYPE_CHECKING from infrastructure.platforms.providers.slack, which does not exist. Pre-existing (reproduced on a git-archive export of HEAD with mypy --no-incremental); the incremental cache usually hides it. The fix is to point the import at integrations.slack.provider, which needs a new contract (e) ignore entry (forbidden) or a contracts type, so it belongs with TASK-26.1 (Slack handler contract).

Gates (from app/): ruff check . -> All checks passed; ruff format --check . -> 742 files already formatted; lint-imports -> 8 kept, 0 broken; rg 'infrastructure[./]operations' app -> 0 hits; mypy -> 70 errors in 25 files, same set as before the move apart from the cache-surfaced dead-import line above (no new errors from this change); pytest tests --ignore=tests/smoke -> 3476 passed, 6 failed (known order leaks in test_webhooks_aws_sns.py and directory/test_google.py); make test -> 2724 passed + 758 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:35
---
2026-09-28 Stack A realignment: TASK-18 cannot declare contract (c) (import-linter forbidden contracts have no optional-module syntax and contracts/ does not exist yet), so this task adds it. The error-code registry this task moves is created by TASK-105.2; provider/operation are dropped by TASK-105.1. Stack A is now 18 -> 105 -> 105.1 -> 105.2 -> 106 -> 26.1 -> 107.
---

created: 2026-09-28 16:45
---
2026-09-28: implementation plan approved by human (Guillaume Charest), given in session. Decisions: test_operations_result.py moves to tests/unit/contracts/operations/ (mirroring production, next to the registry test); the 135-file move stays one PR as a recorded size-gate exception (one-line import rewrite; splitting would need a temporary re-export shim or leave main broken).
---
<!-- COMMENTS:END -->
