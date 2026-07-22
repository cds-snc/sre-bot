---
id: TASK-13
title: Converge every surface on Python 3.14
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-22 19:01'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies: []
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1267'
priority: high
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Python). Today: CI pins 3.11, the venv is 3.12, the Docker image runs python:3.14-slim, and ruff/mypy target 3.11 - production runs an interpreter two minors ahead of everything that tests the code.

Steps:
1. Set .python-version to 3.14 (create if absent, at app/ working root).
2. Update every GitHub Actions workflow python-version to 3.14.
3. Confirm the Dockerfile base stays python:3.14-slim.
4. Set requires-python = ">=3.13" (no upper bound) in app/pyproject.toml; set ruff target-version and mypy python_version to 3.14 equivalents.
5. Recreate the local venv on 3.14 (uv python pin + uv sync); run the full test suite on 3.14 and fix any incompatibilities found.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep across .python-version, workflows, and Dockerfile shows exactly one Python version: 3.14
- [ ] #2 CI runs green on 3.14
- [ ] #3 ruff and mypy target versions match
- [ ] #4 grep across .devcontainer/docker-compose.yml shows VARIANT: "3.14" (matches .devcontainer/Dockerfile's ARG default, no more silent 3.12 override)
<!-- AC:END -->



## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Pin the interpreter: from app/, run `uv python pin 3.14` (writes app/.python-version with `3.14`). Un-ignore it: add `!app/.python-version` immediately after the blanket `.python-version` entry in .gitignore (root .gitignore currently ignores all `.python-version` files repo-wide, which would silently drop this file from any commit and break AC#1's grep).

2. .github/workflows/ci_code.yml: change the `actions/setup-python` step's `python-version: "3.11"` to `python-version: "3.14"`. This is the only workflow in the repo that references a Python version (grep confirmed: no other workflow under .github/workflows sets up Python directly; ci_container.yml/build_and_deploy.yml build the Dockerfile, which already pins 3.14).

3. Dockerfile (root): no change required — already `FROM python:3.14-slim@sha256:...`. Verify the digest pin still resolves to a current 3.14-slim image (informational only, do not change unless it fails to pull).

4. .devcontainer/docker-compose.yml: change the `app` service's build arg `VARIANT: "3.12"` to `VARIANT: "3.14"` so the devcontainer matches .devcontainer/Dockerfile's own `ARG VARIANT="3.14"` default (today docker-compose silently overrides it back down to 3.12 — a second lagging surface caught during research, added to scope per human confirmation).

5. app/pyproject.toml:
   - `requires-python = ">=3.11"` -> `requires-python = ">=3.13"` (matches decisions/toolchain.md: floor, no upper bound; deliberately not literal "3.14" since it is a minimum-version constraint, not a pin — do not include this line in AC#1's literal-3.14 grep).
   - `[tool.ruff] target-version = "py311"` -> `"py314"`.
   - `[tool.mypy] python_version = "3.11"` -> `"3.14"`.
   - Leave `[tool.Makefile]`/black's `--target-version py311` (app/Makefile `fmt`/`fmt-ci`) untouched: black is scheduled for full removal under TASK-15 (decisions/toolchain.md migration ticket), so retargeting a tool being deleted is wasted churn — note this explicitly in the PR description so reviewers don't flag it as missed.

6. Regenerate the lock and venv: `cd app && uv lock` (re-resolves against the new requires-python floor) then `uv sync --extra dev` (rebuilds `.venv` on 3.14 via the new `.python-version`). Confirm `uv run python --version` reports 3.14.x.

7. Run the full gate locally on the 3.14 venv and fix any *newly introduced* incompatibilities (do not fix pre-existing, unrelated failures):
   - `uv run ruff check .`
   - `uv run mypy . --check-untyped-defs --explicit-package-bases` (baseline: 123 pre-existing errors in app/modules/ legacy tree, unrelated to the interpreter bump — confirmed identical under 3.11 config executed via a 3.14 interpreter during planning research; CI already tolerates this via `make lint-ci`'s `mypy ... || true`, out of scope for this task per TASK-15/toolchain.md migration notes)
   - `uv run black --check .` (confirmed clean under 3.14 during planning research)
   - `uv run pytest tests --ignore=tests/smoke` (confirmed 2855 passed / 37 skipped under 3.14 during planning research, zero regressions vs. the 3.12 baseline — only pre-existing deprecation warnings, e.g. `datetime.utcnow()`, pytest-asyncio event-loop-policy, unrelated to this task)

8. Push CI and confirm the `Lint, format and test code` workflow (ci_code.yml) is green end to end on the 3.14 setup-python step.

Planning-research findings (de-risking, not implementation steps):
- Installed cpython 3.14.5 locally via `uv python install 3.14` and ran `uv sync --python 3.14 --extra dev`: all locked dependencies (including compiled extras) resolved and installed cleanly, zero version-compat blockers.
- Full ruff check: clean. Full black --check: clean. Full pytest (unit+integration+legacy, matching `make test`): 2855 passed, 37 skipped, no failures.
- mypy under the existing 3.11-targeted config surfaced the same 123 pre-existing errors in app/modules/ that already exist on 3.12 today (per repo memory: "mypy/flake8 gates currently fail on pre-existing repo-wide issues") — not a 3.14 regression, and not gated in CI today (`|| true`).
- Conclusion: this task is pure config/toolchain convergence with no code changes anticipated. Local venv was restored to 3.12 after research (`uv sync --python 3.12 --extra dev`) to leave the sandbox as found; the actual cutover happens in step 6 above during implementation.

AC/step traceability:
- AC#1 (single 3.14 version via grep) <- steps 1, 2, 3, 4.
- AC#2 (CI green on 3.14) <- steps 2, 6, 7, 8.
- AC#3 (ruff/mypy target versions match) <- step 5.
- DoD#1 (full suite passes on 3.14 locally + CI) <- steps 6, 7, 8 (pre-validated in research; re-run for real during implementation since research used a throwaway venv).
- DoD#2 (PR references decisions/toolchain.md) <- human/PR-description action, not a code step.

Blast radius / rollback:
- Touches only toolchain/config surfaces (.gitignore, one GH workflow, root Dockerfile verification only, devcontainer compose, app/pyproject.toml, app/uv.lock, app/.python-version). No application code paths change.
- Rollback is a straight revert of the single PR; no data migrations, no runtime schema/API changes, no deployed-service behavior change (production Docker image was already 3.14 before this task).
- Residual risk: CI runners' `actions/setup-python@v4.8.0` must have a 3.14 build available in its cache/index; if not, bump the action version pin (currently a 2023-era v4.8.0) — check during implementation if the workflow fails to resolve the interpreter.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Full test suite passes on 3.14 locally and in CI
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->
