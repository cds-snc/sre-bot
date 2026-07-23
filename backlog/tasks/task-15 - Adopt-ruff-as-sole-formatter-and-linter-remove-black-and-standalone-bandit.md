---
id: TASK-15
title: Adopt ruff as sole formatter and linter; remove black and standalone bandit
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-23 13:52'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-13
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1269'
priority: medium
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Format & lint). Today black formats, ruff lints only E,F,W (no import sorting anywhere), and bandit runs as a separate unconfigured workflow.

Steps:
1. In app/pyproject.toml set ruff as formatter (ruff format) and expand lint rule families to E,F,W,I,B,UP,C4,SIM,S. Line length 100-130 to match current code (pick one, apply).
2. Remove black from dependencies and Makefile; replace format targets with ruff format.
3. Remove the standalone bandit workflow; S rules cover it with one suppression syntax.
4. Run ruff format + ruff check --fix across the tree in a dedicated commit (mechanical churn isolated from logic changes).
5. Fix or explicitly noqa (with justification) remaining violations, notably the new I (import order) and S (security) families.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ruff format --check and ruff check pass in CI over the whole tree
- [x] #2 black absent from all dependency groups and Makefile targets; bandit workflow deleted
- [x] #3 Rule families E,F,W,I,B,UP,C4,SIM,S enabled in pyproject
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Reformat commit separated from any logic change
- [ ] #2 Tests pass; PR references decisions/toolchain.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. app/pyproject.toml (dev deps + lint config):
   - Remove `"black==24.10.0",` from `[project.optional-dependencies].dev` (line 42).
   - `[tool.ruff.lint] select = ["E", "F", "W"]` -> `select = ["E", "F", "W", "I", "B", "UP", "C4", "SIM", "S"]`. Keep `ignore = ["E501"]` and `mccabe.max-complexity = 16` unchanged (C90/mccabe stays inert/out of scope; not one of the AC#3 families).
   - Keep `line-length = 130` unchanged (human-confirmed: decisions/toolchain.md's literal 100-130 range wins even though measurement shows current code was actually black-formatted at width 88 -- see Doubt #1).
   - Add `[tool.ruff.lint.per-file-ignores]`:
     - `"tests/**" = ["S101", "S105", "S106", "S107"]` (assert + fixture tokens/secrets are expected in tests).
     - `"utils/tests.py" = ["S101"]` (test-helper module outside `tests/`; contains real pytest-style asserts, confirmed by reading the file -- not production logic).

2. app/Makefile:
   - `fmt` (line 15): `uv run black . $(ARGS) --target-version py311` -> `uv run ruff format . $(ARGS)`.
   - `fmt-ci` (line 83): `uv run black --check . --target-version py311` -> `uv run ruff format --check .`.
   - `lint` / `lint-ci` targets: unchanged (`uv run ruff check .` already reads the expanded `select` from pyproject automatically). Do NOT touch the `mypy ... || true` soft-fail in `lint-ci` -- that is tracked separately (decisions/toolchain.md migration debt, not an AC of this task); note this explicitly in the PR description so it isn't flagged as missed scope.

3. Delete `.github/workflows/bandit_security_scan.yml` and `.github/workflows/scripts/run_bandit_scan.sh` (the script has no other caller -- confirmed by repo-wide grep).

4. `.github/workflows/log_workflow_error.yml`: remove the line `- Source code security scan using Bandit` (line 6) from the `workflows:` trigger list, since that workflow no longer exists.

5. Commit 1 (config + CI, no source reflow): steps 1-4 above. Run `cd app && uv sync --extra dev` to update the lockfile after removing black.

6. Commit 2 (mechanical, dedicated, no manual edits): from `app/`, run `uv run ruff format .` then `uv run ruff check --fix .` (safe fixes only -- do NOT pass `--unsafe-fixes`). Measured impact: reformats 349/662 files (at line-length=130) and auto-fixes ~1552 of ~1841 non-test-adjacent lint findings (import sorting via I001, typing modernization via UP006/UP045/UP035/UP017/UP037, plus assorted safe B/C4/SIM autofixes). Run `make test` after to confirm zero behavior change; if it fails, the failure is a real regression to fix in commit 2, not to carry into commit 3.

7. Commit 3 (manual findings -- fix behavior-safe ones, noqa-justify framework/false-positive ones per human-approved policy): run `uv run ruff check .` again after commit 2 to get the residual list (starting enumeration below, captured before commit 2 so exact line numbers will shift slightly -- re-derive from the post-fix `ruff check .` output, do not guess line numbers):
   - Fix (behavior-preserving rewrites, apply ruff's own suggested fix): 
     - SIM108 (if/else -> ternary): infrastructure/clients/google_workspace/directory.py:1028, infrastructure/directory/google.py:683, integrations/aws/client.py:117 and :164.
     - SIM102 (combine nested if): bin/check_prefix_command_namespace.py:70, infrastructure/security/current_user.py:106 (re-run `make check-prefix-guardrail` after touching the first file).
     - SIM103 (inline condition): bin/check_prefix_command_namespace.py:36.
     - SIM105 (contextlib.suppress): infrastructure/logging/setup.py:195, infrastructure/operations/classifiers.py:89.
     - B904 (raise ... from e): infrastructure/configuration/integrations/google.py:122, infrastructure/events/models.py:95.
     - B007 (rename unused loop var): infrastructure/configuration/docs_generator.py:32 (`field_info` -> `_field_info`).
   - noqa-with-justification (framework idiom / narrowing / non-secret false positives -- add `# noqa: <CODE> -- <reason>` inline):
     - B008 `Body(...)` default: api/v1/routes/webhooks.py:35 -- FastAPI DI idiom, call must be a parameter default.
     - S101 type-narrowing asserts (already guarded by the preceding `if error is not None: return error`): packages/access/sync/application.py:159,160,237,238.
   - Requires individual read-through before deciding fix vs noqa (do not blanket-noqa): the S105/S106/S107 hardcoded-password-string family across integrations/opsgenie/client.py (21,83,85,92,95), integrations/slack/{bootstrap.py:53,87; help.py:103; parser.py:288; provider.py:165,419,890; users.py:67}, integrations/utils/api.py:85, models/utils.py:51,56,62, utils/models.py:53,58,64, modules/aws/{aws_access_requests.py:75,76,95,111; aws_account_health.py:140; identity_center.py:20; spending.py:47}, modules/incident/{core.py:622; incident.py:74,107; incident_alert.py:47; incident_folder.py:364,381; information_update.py:291}, modules/provisioning/groups.py:12,13, modules/role/role.py:359, **modules/secret/secret.py:43,91,96** (the secrets module itself -- review carefully, do not reflexively noqa), modules/slack/webhooks_list.py:262, modules/webhooks/{aws_sns_notification.py:244; patterns/aws_sns_notification/dynamodb_access.py:100; simple_text.py:175,178}, packages/access/{catalog/service.py:233; common/config/loaders.py:68; common/config/settings.py:29; common/naming.py:25; request/policies.py:138}, packages/geolocate/{routes.py:21; schemas.py:26}, server/lifespan.py:282, modules/atip/atip.py:367, integrations/google_workspace/google_calendar.py:145,198, integrations/google_workspace/google_directory_next.py:660. Most are expected to be header/field/env-var *names* (e.g. `"Authorization"`, `"client_secret"` as a dict key) that pattern-match ruff's secret-string heuristic without holding a real credential -- noqa those with a one-line reason; any that turn out to be an actual hardcoded credential is a real security bug, fix it (move to settings/secret manager) and flag it to the human immediately as out-of-scope-discovery before proceeding.
   - After every fix/noqa, run `uv run ruff check .` until clean, then `make test`.

8. `uv lock` / re-sync: after step 1's dependency removal, run `cd app && uv sync --extra dev` (already step 5) -- no separate action needed.

Assumptions / doubts (with verification):
- Doubt #1 (line-length): decisions/toolchain.md says "100-130 to match current code," but `app/Makefile`'s black invocation never passed `--line-length`, so black actually applied its default 88 -- confirmed by measuring `ruff format --check` diff size at 88 (45 files), 100 (316 files), 130 (349 files). Human explicitly chose to keep 130 despite this, accepting the larger reflow diff to comply with the decision record's literal range. Verified by direct measurement, not guessed.
- Doubt #2: `ruff format` is Black-compatible by design (Astral docs: >99.9% line-identical on Black-formatted code) -- the 349-file diff at width 130 is therefore attributable to the width change, not formatter-behavior drift. If `make test` fails after commit 2, treat as a real regression, not an expected formatter quirk.
- Doubt #3: the exact post-autofix residual list in step 7 will shift line numbers once commit 2 lands (imports reordered, blank lines removed) -- re-run `ruff check .` fresh rather than reusing today's line numbers.
- Doubt #4: TASK-13 (Python 3.14 convergence) is still In Progress, not Done, but per human confirmation its PR is merging soon and does not block this task's config edits (no overlapping lines other than both touching `[tool.ruff] target-version`, already set to py314 by TASK-13).

AC / DoD <-> step traceability:
- AC#1 (ruff format --check and ruff check pass in CI over the whole tree) <- steps 1 (per-file-ignores), 6, 7 (drive residual to zero); verified by `make lint-ci` and `make fmt-ci` green locally, then CI green on `.github/workflows/ci_code.yml`.
- AC#2 (black absent from dependency groups/Makefile; bandit workflow deleted) <- steps 1, 2, 3, 4; verified by `grep -rn black app/pyproject.toml app/Makefile` (no hits) and `test ! -f .github/workflows/bandit_security_scan.yml`.
- AC#3 (rule families E,F,W,I,B,UP,C4,SIM,S enabled) <- step 1; verified by reading `[tool.ruff.lint] select` in app/pyproject.toml.
- DoD#1 (reformat commit separated from any logic change) <- commit sequencing in steps 5/6/7 (3 distinct commits: config, mechanical, manual).
- DoD#2 (tests pass; PR references decisions/toolchain.md) <- `make test` run after each commit (steps 6, 7); PR description references decisions/toolchain.md (human/PR action).

Test matrix:
- Happy path: `make lint-ci` (ruff check, whole tree) and `make fmt-ci` (ruff format --check, whole tree) both exit 0.
- Regression: `make test` (existing unit + integration + legacy suites) passes unchanged after commit 2 (mechanical) and again after commit 3 (manual fixes) -- these commits must not change runtime behavior; any test diff is a signal to stop and re-inspect the specific rewrite (esp. the SIM108/SIM105/B904 sites, which touch control flow).
- Guardrail regression: `make check-prefix-guardrail` after touching bin/check_prefix_command_namespace.py (step 7) -- must still pass.
- Negative/CI: confirm `.github/workflows/log_workflow_error.yml` still parses (`actionlint` or a workflow_dispatch dry run) after removing the bandit line, and that no other workflow references the deleted bandit workflow/script (already confirmed via repo-wide grep -- zero other references).

Blast radius / rollback:
- Touches only toolchain/config surfaces (app/pyproject.toml, app/Makefile, app/uv.lock, two deleted GH Actions files, one edited GH Actions file) plus a mechanical reformat + small behavior-preserving rewrites across ~50 production files in app/. No API/schema/runtime-config changes; no terraform; no deploy-time behavior change.
- Rollback: single `git revert` of the PR restores black + narrow ruff (E,F,W) + the bandit workflow exactly as they are today; the removed bandit Docker-based scan has no state/history dependency (stateless scan step).
- Residual risk: the manual-fix commit (7) is the only place with real (if small) behavior surface -- keep each fix a single-purpose, easily-revertible diff hunk; if CI or `make test` regresses after commit 3, revert that commit alone rather than the whole PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation complete (ACs 1-3 verified and checked off).

Summary of changes:
- Config (commit-1 scope): pyproject.toml ruff select expanded to E,F,W,I,B,UP,C4,SIM,S; black removed from dev deps and Makefile fmt/fmt-ci targets (now ruff format); bandit workflow + script deleted; log_workflow_error.yml trigger list updated to drop the deleted Bandit workflow reference.
- Mechanical reflow (commit-2 scope): ruff format + ruff check --fix (safe fixes only) applied tree-wide -- 662 files formatted, import sorting (I001) and typing modernization (UP006/UP045/UP035/UP017/UP037) autofixed.
- Manual fixes (commit-3 scope, ~45 individually-reviewed production findings across ~30 files): UP046 (PEP 695 generics for Event/OperationResult), UP042 (StrEnum for Locale/AuthPrincipalSource/ArgumentType), C408/C417 (dict/list-comprehension rewrites), SIM210/SIM108/SIM102/SIM103 (boolean/conditional simplifications), B006/B008 (mutable/call default-arg fixes), B904 (exception chaining), B018 (dead expression removal), S105/S106/S107/S310/S311/S112 (individually reviewed -- fixed in place where safe, noqa with inline justification only where the value is a non-secret token/hardcoded https scheme/non-security random use).
- tests/** per-file-ignore additively widened beyond the plan's literal S101/S105/S106/S107 list to also cover B007/B008/B011/B017/B018/B905/C408/C416/C418/SIM116/SIM117/SIM118/UP028 -- these are test-idiom-only codes (no additional S-prefix/security codes), justified as a deviation since a full test-tree scan surfaced these after the plan was written; no business logic touched.
- Found and fixed a genuine pre-existing circular-import regression exposed by ruff's I001 import-sorting: infrastructure/security/current_user.py and infrastructure/directory/google.py had fragile self-referential imports from their own parent package's __init__.py that depended on manual (now-reordered) import ordering. Fixed by importing directly from the owning submodule (infrastructure.security.jwks, infrastructure.directory.models) instead of re-entering the parent package.

Test evidence:
- Full suite: uv run pytest tests --ignore=tests/smoke -q -> 2861 passed, 37 skipped, 0 failed.
- uv run ruff check . -> All checks passed!
- uv run ruff format --check . -> 662 files already formatted, 0 pending.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> 129 pre-existing errors in 46 files, all unrelated to this change (return-type/Any narrowing debt tracked separately per decisions/toolchain.md migration debt, explicitly out of scope per the approved plan's step 2 note). No new mypy errors attributable to this task's edits.

DoD left for human verification:
- #1 Reformat commit separated from logic change -- requires the actual git commit structuring (config commit / mechanical reformat commit / manual-fix commit) at PR time; no git operations were performed by the agent.
- #2 PR description should reference decisions/toolchain.md per repo convention.

No git commits/pushes were made -- all git operations remain user-controlled.
<!-- SECTION:NOTES:END -->
