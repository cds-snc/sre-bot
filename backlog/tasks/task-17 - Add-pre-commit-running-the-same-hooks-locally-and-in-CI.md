---
id: TASK-17
title: Add pre-commit running the same hooks locally and in CI
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 19:31'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-15
  - TASK-16
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1271'
priority: medium
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (CI gates). No .pre-commit-config.yaml exists today.

Steps:
1. Create .pre-commit-config.yaml with: ruff format, ruff check, mypy (via local hook running the project venv so versions match), uv lock --check, plus standard hygiene hooks (end-of-file, trailing whitespace, YAML syntax).
2. CI job runs pre-commit run --all-files (or prek, its config-compatible successor - pick one and note it in the config header).
3. Document the one-time local setup (pre-commit install) in the README developer section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 .pre-commit-config.yaml exists; pre-commit run --all-files passes locally
- [ ] #2 CI has a job running the same hooks over all files
- [ ] #3 Hook tool versions match the project versions (mypy/ruff run from the project environment)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 README documents setup
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ordered steps (files grounded via repo research on 2026-07-24):

1. app/pyproject.toml: add `pre-commit==4.6.1` (latest PyPI release) to `[project.optional-dependencies] dev` list (after `checkov`, before `setuptools==78.1.1`, alphabetical grouping not enforced elsewhere in this list so append is fine). This makes pre-commit itself a version-pinned, uv-managed dev tool instead of a global pipx/pip install, so `uv run --project app pre-commit ...` always resolves the exact pinned version from app/uv.lock (directly satisfies AC#3's "run from the project environment" for the pre-commit binary itself).
2. Run `cd app && uv lock` to regenerate app/uv.lock with the new dev dependency (mechanical, not hand-reviewed line-by-line).
3. Create `.pre-commit-config.yaml` at the repo root (new file) with:
   - repo: local
     - id: ruff-check, name: "ruff check --fix", entry: `uv run --project app ruff check --fix`, language: system, types: [python], files: `^app/`
     - id: ruff-format, name: "ruff format", entry: `uv run --project app ruff format`, language: system, types: [python], files: `^app/`
     - id: mypy, name: "mypy (project venv)", entry: `bash -c 'uv run --project app mypy . --check-untyped-defs || true'`, language: system, pass_filenames: false, always_run: true, files: `^app/` — see Doubt #2 below on why `|| true` stays for now.
     - id: uv-lock-check, name: "uv lock --check (app/)", entry: `uv lock --check --project app`, language: system, pass_filenames: false, always_run: true
   - repo: https://github.com/pre-commit/pre-commit-hooks, rev: v6.0.0 (latest tag, confirmed via GitHub releases 2026-07-24):
     - id: end-of-file-fixer
     - id: trailing-whitespace
     - id: check-yaml
   Header comment notes: "pre-commit (not prek) chosen; local hooks call `uv run --project app` so hook tool versions are always the app/pyproject.toml-pinned ones, never an independently-versioned mirror repo — this is the direct fix for the drift diagnosed 2026-07-24 (CI caught I001 import-sort violations that a local run had missed)."
4. .github/workflows/ci_code.yml: replace the two separate `Lint` (`make lint-ci`) and `Format` (`make fmt-ci`) steps with a single step: `working-directory: ./app` unset (must run from repo root since config is root-level), `run: uv run --project app pre-commit run --all-files`. Keep it positioned after the existing `Install dev dependencies` step (unchanged, still `make install-dev` from `./app`) so the .venv pre-commit needs already exists, and before the `Test` step (unchanged).
5. README.md: under the existing "## Getting Started (Local Development)" section (lines 80-103), add a new numbered step (after step 3 `uv sync --extra dev`) or a short subsection: "Install the git hook once: `cd app && uv run pre-commit install` (from repo root: `uv run --project app pre-commit install`). Every commit then runs the same ruff/mypy/uv-lock/hygiene checks CI runs." Keep it short, matching existing doc tone.

AC traceability:
- AC#1 (".pre-commit-config.yaml exists; `pre-commit run --all-files` passes locally") -> Steps 1-3; verify: `uv run --project app pre-commit install` then `uv run --project app pre-commit run --all-files` from repo root, zero failures (tree is already ruff-clean per current `make fmt && make lint`).
- AC#2 ("CI has a job running the same hooks over all files") -> Step 4; verify: CI run shows the new step invoking `pre-commit run --all-files` and passing.
- AC#3 ("Hook tool versions match the project versions") -> Steps 1-3 (local hooks call `uv run --project app <tool>`, never a separately-pinned mirror repo for ruff/mypy); verify: hook-invoked `uv run --project app ruff --version` / `mypy --version` match app/pyproject.toml's `ruff>=0.11.0` (locked 0.15.7) and `mypy==1.19.1` pins exactly, because it is literally the same venv.
- DoD#1 ("README documents setup") -> Step 5.
- DoD#2 ("PR references decisions/toolchain.md") -> human PR description, not a code step.

Test matrix (config-only task; no app/tests/*.py unit tests apply -- verification is CLI/CI-based):
- Happy path: stage a file with a deliberately unsorted import block (reproducing the exact I001 incident from 2026-07-24), run `pre-commit run --all-files` -> ruff-check hook fails, autofixes with --fix, rerun is clean.
- Boundary: bump a version string in app/pyproject.toml without relocking -> uv-lock-check hook fails; run `uv lock`; hook passes.
- Failure path: introduce an intentional new type error in an app/ file -> mypy hook surfaces it in output (non-blocking per Doubt #2) without failing the commit; confirms hook actually runs the project's mypy.
- Hygiene: a file missing a trailing newline / with trailing whitespace is auto-fixed by end-of-file-fixer/trailing-whitespace.
- CI parity (regression test for the diagnosed bug): push a branch with the same unsorted-import pattern; confirm CI's new pre-commit step fails identically to the local `pre-commit run --all-files`, proving local and CI can no longer silently disagree.

Assumptions / doubts (need verification or human confirmation):
1. Discovered an existing, git-tracked, second uv project at the repo root (pyproject.toml, uv.lock, .python-version, all committed on main, content near-identical to app/'s) that is NOT part of TASK-44 ("Consolidate dev tooling at the repo root", still To Do) per its own task file. This plan does NOT touch it -- all pre-commit hooks target app/ explicitly via `--project app`/`files: ^app/`. Flagging as out-of-scope discovery per task-execution scope-change rule; recommend a human confirm whether it's intentional before any future task assumes a single root project.
2. mypy hook blocking mode: TASK-16 ("Make mypy blocking with a per-package strict ratchet") is still To Do. `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` currently reports 123 errors across 43 files with no ratchet/ignore-baseline mechanism yet. Making the mypy pre-commit hook hard-blocking today would block nearly any commit touching those 43 files for pre-existing, unrelated errors. Recommendation: keep the mypy hook mirroring today's CI soft-fail (`|| true`), matching decisions/toolchain.md's own stated migration tolerance ("Tolerated until closed: ... soft-fail mypy"), and remove `|| true` as part of TASK-16 once its ratchet baseline lands. Needs explicit human sign-off since it's a deliberate, temporary deviation from the decision record's blocking-CI end state.
3. .devcontainer/devcontainer.json still lists the `ms-python.black-formatter` extension (line ~21) even though black is fully removed (TASK-15.12 status: Done) and this session already switched the default formatter setting to ruff on this branch. Recommend a 1-line removal of that extension entry, bundled into this same PR (same toolchain-config subsystem, trivial) -- pending human confirmation since it's outside TASK-17's literal ACs.
4. Repo-wide sweep for "black" as a forward-looking formatter reference in open backlog tasks (grep across backlog/tasks, 87 matches / 17 files reviewed): no open task instructs relying on black going forward. TASK-13 (open) has exactly one deliberate, correct no-op note ("black is scheduled for full removal under TASK-15 ... retargeting a tool being deleted is wasted churn") -- already correct, no edit needed. All other matches are either TASK-15/15.x migration-narrative content (appropriate: those tasks describe removing black, so they must mention it) or historical completion-note quotes on already-Done tasks (task-45.1, task-45.4 quoting "uv run black --check . -> pass" as an audit-trail record of what was actually run at that time). Per backlog-tasks instructions, task markdown is CLI-owned and these are historical records, not forward-looking instructions -- no task edits proposed.
5. Assumes CI's `pipx install uv` (unpinned in ci_code.yml) resolves a uv version supporting `--project` (confirmed available in locally-installed uv 0.11.31; the flag has existed for a while, so risk is low) -- verify by checking the resolved `uv --version` in the CI job log during implementation.
6. Assumes the pre-commit-hooks v6.0.0 hygiene hooks (end-of-file-fixer, trailing-whitespace, check-yaml) produce no unwanted reformatting across non-app/ directories (backlog/, terraform/, docs/) when run `--all-files` repo-wide -- verify by running `pre-commit run --all-files` once locally and inspecting the diff before committing; scope hooks repo-wide unless that check reveals a conflict.

Blast radius and rollback:
- .pre-commit-config.yaml (new): zero runtime effect; opt-in locally via `pre-commit install`, only exercised in CI via the new step. Deleting the file (or `git revert`) fully removes the hook.
- app/pyproject.toml + app/uv.lock: additive-only change to `[project.optional-dependencies] dev`, excluded from production installs (`uv sync --locked --no-dev`) -- zero production blast radius.
- .github/workflows/ci_code.yml: replaces two CI steps with one; if the new step misbehaves, a single `git revert` of this file restores the previous two-step Lint/Format jobs -- CI-only impact, no deployment risk.
- README.md: documentation-only.
- Overall: a single `git revert` of the whole PR fully and safely restores current behavior; no ordering constraints, no env vars, no terraform involved.

Size-gate verdict: fits one PR. Diff is ~40-60 new YAML lines + 1-line pyproject.toml addition + mechanical uv.lock regen + ~10-line CI workflow edit + ~15-line README addition (+ optional 1-line devcontainer cleanup pending confirmation). Single subsystem (toolchain/CI config only, no application code, no terraform, no mixed refactor+behavior). No decomposition required.
<!-- SECTION:PLAN:END -->
