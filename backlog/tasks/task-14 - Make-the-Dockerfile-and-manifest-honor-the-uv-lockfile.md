---
id: TASK-14
title: Make the Dockerfile and manifest honor the uv lockfile
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 18:51'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-13
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1268'
priority: high
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Packaging). Today the Dockerfile copies uv.lock optionally (glob uv.lock*) then runs uv pip install --system -e . - discarding every property the lockfile buys. Runtime deps are ==-pinned in [project] (exactness belongs in uv.lock), awscli ships as a runtime dep, dev deps sit in [project.optional-dependencies], and stale hatch/Makefile references to the deleted core package linger.

Steps:
1. Rewrite the Dockerfile multi-stage: builder stage runs uv sync --locked --no-dev (non-editable); runtime stage copies the venv/site-packages. COPY uv.lock without a glob so a missing lock fails the build.
2. In app/pyproject.toml: loosen [project] dependencies to ranges (exactness lives in uv.lock); move dev tools to PEP 735 [dependency-groups]; remove awscli from runtime deps; delete stale core references in [tool.hatch.build.targets.wheel] and the Makefile coverage targets.
3. Add uv lock --check and uv sync --locked steps to CI.
4. [project] carries name, static version, description, readme, license (SPDX), requires-python, dependencies, [project.urls]; runtime revision identity is GIT_SHA env.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dockerfile is multi-stage, installs with uv sync --locked --no-dev, and fails to build without uv.lock
- [ ] #2 No == pins remain in [project] dependencies; dev deps live in [dependency-groups]; awscli is gone from runtime deps
- [ ] #3 CI fails when uv.lock is out of date (uv lock --check step)
- [ ] #4 grep -rnw "core" app/pyproject.toml app/Makefile shows no stale references to the deleted core package (botocore/google-api-core dependency names are expected non-matches, not the deleted package)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Image builds and the container boots (smoke: readiness endpoint responds)
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Root `Dockerfile` — rewrite as two-stage, both stages `FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd` (keep the existing pinned digest):
   - **builder** stage: `WORKDIR /app`; `RUN pip install --no-cache-dir uv`; `COPY app/pyproject.toml app/uv.lock ./` (no glob — a missing `uv.lock` now fails the build at this COPY, satisfying AC#1's "fails to build without uv.lock"); `RUN uv sync --locked --no-dev --no-install-project` (dependency-only layer, cacheable); `COPY app/ .`; `RUN uv sync --locked --no-dev` (this second, no-flag-restricted sync installs the `sre-bot` project itself **non-editable** into the same `.venv` — required per decisions/plugins.md: `load_setuptools_entrypoints` reads installed-distribution metadata, so the image must have the project installed as a distribution, not just its dependencies, or entry-point plugin discovery silently loads zero plugins and — per plugins.md's "Failure is fatal" — crashes the lifespan).
   - **runtime** stage: fresh `FROM` the same base+digest. Install the `aws` CLI to keep `app/bin/entry.sh`'s `aws ssm get-parameter` calls working after `awscli` leaves `[project] dependencies` (an OS-level tool for that script, not a Python/uv-managed dependency — stays out of `pyproject.toml`/`uv.lock` per AC#2 while keeping the container bootable). **Researched via AWS's own docs** (fetched `getting-started-install.html`/`getting-started-version.html`) instead of guessing: AWS explicitly does **not** recommend third-party/distro repos ("we can't guarantee they contain the latest version") and Debian bookworm's default repos don't carry an `awscli` package at all (confirmed: `apt-cache policy awscli` → "Unable to locate package" against a bookworm base) — so `apt-get install awscli` is not viable here. AWS's own documented "good option for version control" path is **the command-line installer, version-pinned, with GPG signature verification** against AWS's published, long-lived signing key (Key ID `A6310ACC4672475C`, expires 2027-07-01) — this is the industry-standard approach for reproducible, integrity-checked installs in a Dockerfile, and mirrors this task's own reproducibility goal (pinned lockfile) applied to the one non-uv-managed runtime tool:
     - Add a new repo-root file `aws-cli-pubkey.asc` containing AWS CLI Team's public PGP key block (verbatim from AWS's official docs, reviewable in the PR diff).
     - `ARG AWSCLI_VERSION` with a default pinned to the current stable AWS CLI v2 release **at implementation time** (verify via the changelog at `https://github.com/aws/aws-cli/blob/v2/CHANGELOG.rst` — do not fabricate a version number; confirm the exact current release when this step is actually implemented).
     - `RUN apt-get update && apt-get install -y --no-install-recommends curl unzip gnupg && curl -fsSL -o awscliv2.zip "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" && curl -fsSL -o awscliv2.sig "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip.sig" && gpg --import aws-cli-pubkey.asc && gpg --verify awscliv2.sig awscliv2.zip && unzip awscliv2.zip && ./aws/install && rm -rf awscliv2.zip awscliv2.sig aws aws-cli-pubkey.asc && apt-get purge -y --auto-remove curl unzip gnupg && rm -rf /var/lib/apt/lists/*` — build fails closed if the signature doesn't verify (`gpg --verify` exits non-zero) or the version-pinned URL 404s.
     - Confirmed unambiguous architecture: no `runtime_platform` override in `terraform/ecs.tf` → Fargate defaults to X86_64/LINUX, so `awscli-exe-linux-x86_64` (not `-aarch64`) is correct.
   - `COPY --from=builder /app /app` (carries the `.venv` — including the installed project + entry-point metadata — and the app source in one copy); `ENV PATH="/app/.venv/bin:$PATH"`; keep the existing `ARG git_sha` / `ENV GIT_SHA=$git_sha`, the GeoDB tar extraction block, and the `COPY app/bin/entry.sh /app/entry.sh` + `ENTRYPOINT` exactly as today (unrelated to packaging, preserve verbatim).

2. `app/pyproject.toml`:
   - `[project] dependencies`: change every `==`-pinned entry to a lower-bound-only range (`pkg==X.Y.Z` → `pkg>=X.Y.Z`, no upper bound — mirrors `requires-python`'s own no-upper-bound convention since toolchain.md doesn't specify a narrower band); remove the `"awscli==1.44.44"` line entirely; leave `PyYAML!=6.0.0,!=5.4.0,!=5.4.1` untouched (already not a `==` pin).
   - `[dependency-groups] dev = [...]`: **no change** — already PEP 735 (not `[project.optional-dependencies]` as the task's Description claims; that part of the task is already done, confirmed by reading the live file. Flagging this as a stale-description finding, not re-doing it).
   - `[tool.hatch.build.targets.wheel] packages = [...]`: drop the stale `"core"` entry only (leave `api, infrastructure, integrations, jobs, models, modules, packages, server, utils` as-is — out of this task's scope).
   - Confirm `[project]` already carries name/version/requires-python/`[project.urls]` — no readme/license/license-files fields exist today; adding them is Description Step 4's aspiration but is **not covered by any AC**, so out of scope for this slice (flagged as a follow-up candidate, not filed automatically per single-task-scope rule).

3. `app/uv.lock` — regenerate mechanically via `uv lock` after step 2's edits (do not hand-edit; a relaxed lower bound plus `awscli` removal will re-resolve `botocore`/`boto3`/other transitive versions — re-run the full test suite after regeneration to catch any transitive-version drift, per Checks below).

4. `app/Makefile`:
   - Line 66 (`test-coverage-unit`): drop the stale `--cov=core` flag (keep `--cov=modules --cov=api`) — this is the only "core" hit in this file (AC#4).
   - Add two new targets: `lock-check:` → `uv lock --check`, and `install-ci: lock-check` → `uv sync --locked` (installs the default + dev dependency-groups strictly from the committed lock, failing fast if it's stale). Leave `install`/`install-dev`/`dev-setup` untouched for local iteration (they intentionally may still refresh the lock).

5. `.github/workflows/ci_code.yml` — change the existing "Install dev dependencies" step's `run: make install-dev` to `run: make install-ci` (now runs `uv lock --check` then `uv sync --locked`, per decisions/toolchain.md's Checks: "CI: uv lock --check, uv sync --locked"). No other workflow touches Python packaging (`ci_container.yml`/`build_and_deploy.yml` only build/push the already-rewritten Dockerfile).

6. `README.md:96` (`cd app && uv sync --extra dev`) — one-line fix to `cd app && uv sync` (the `--extra` flag is stale from before dev tools moved to `[dependency-groups]`; plain `uv sync` already includes the default `dev` group). Small, directly coupled to this task's own mechanism change — flagged as an in-PR drive-by rather than a separate follow-up, since leaving it would document a command that no longer matches the manifest this task rewrites.

## AC/step traceability
- AC#1 (multi-stage, `uv sync --locked --no-dev`, fails without `uv.lock`) ← step 1.
- AC#2 (no `==` pins in `[project]` deps; dev deps in `[dependency-groups]`; awscli gone from runtime deps) ← step 2 (dev-deps clause already satisfied pre-existing, verified not re-done).
- AC#3 (CI fails when `uv.lock` is stale) ← steps 4, 5.
- AC#4 (no stale "core" references) ← steps 2, 4. AC#4's grep already tightened to word-bounded `grep -rnw "core"` so `botocore`/`google-api-core` don't count as false failures.
- DoD#1 (image builds, container boots, readiness responds) ← step 1; verify locally: `docker build --build-arg git_sha=test -t sre-bot:test .` then `docker run --rm -p 8000:8000 --entrypoint sh sre-bot:test -c "uvicorn main:server_app --host 0.0.0.0"` (bypasses `entry.sh`'s real-AWS SSM fetch, which needs live credentials/parameters unavailable in this check) and `curl localhost:8000/health`; separately confirm `docker run --rm sre-bot:test aws --version` to prove the GPG-verified install actually landed a working binary. The health check also doubles as the plugin-loading regression check: per plugins.md "Failure is fatal", a broken non-editable project install (entry points unresolved) would crash the lifespan before `/health` ever responds.
- DoD#2 (PR references decisions/toolchain.md) ← human PR-description action, not a code step.

## Test matrix
- `docker build` (root) from a clean checkout with `uv.lock` present → succeeds.
- `docker build` with `app/uv.lock` deleted/renamed → fails at the `COPY app/pyproject.toml app/uv.lock ./` step (no glob fallback).
- `docker build` with a deliberately corrupted `awscliv2.zip` (or the wrong `AWSCLI_VERSION` guessed as a smoke test) → fails at `gpg --verify` (fail-closed check).
- Local: `cd app && uv lock --check` → passes after regeneration in step 3.
- Local: `cd app && uv sync --locked --no-dev` → succeeds, matches builder stage.
- `grep -n "==" app/pyproject.toml` under `[project] dependencies` → zero hits (excluding the untouched `PyYAML!=...` line, which has no `==`).
- `grep -rn "awscli" app/pyproject.toml app/uv.lock` → zero hits.
- `grep -rnw "core" app/pyproject.toml app/Makefile` (tightened AC#4 check) → zero hits.
- Full local gate: `uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run pytest tests --ignore=tests/smoke` on the regenerated lock/venv — confirm zero regressions from the dependency-range relaxation (transitive version drift is the main risk here).
- CI dry run: push a branch with `app/uv.lock` deliberately one commit stale to confirm `make install-ci` fails the job (manual one-off verification, not a permanent test).
- Manual DoD#1 smoke steps as above, plus `aws --version` in the built image.

## Assumptions / doubts flagged for human review
- **awscli replacement mechanism (revised after research)**: confirmed via AWS's own install docs + a live `apt-cache policy awscli` check against a bookworm base that Debian does not package `awscli` and AWS explicitly discourages third-party/distro repos for it. Switched the plan to AWS's own documented reproducible path: the version-pinned command-line installer (`awscli-exe-linux-x86_64-<version>.zip`) with GPG signature verification against AWS's published public key (checked into the repo as `aws-cli-pubkey.asc`). This is more setup than a one-line `apt-get install`, but it's the actual AWS-recommended mechanism for exactly this reproducibility/integrity need — flagging for sign-off since it's still a judgment call the task text doesn't dictate, and it introduces one new small committed file.
- **Exact `AWSCLI_VERSION` pin**: deliberately left as "verify at implementation time" rather than guessed now, to avoid baking in a possibly-wrong/soon-stale version number into a plan that isn't executed immediately.
- Dev-dependency-groups migration (Description Step 2's "[project.optional-dependencies]" framing) was already done in a prior pass — not re-verified against a specific prior task, just confirmed against the live file.
- README.md one-line fix folded into this PR (see step 6) rather than filed separately — flagging in case the reviewer prefers it split out.

## Blast radius / rollback
- Touches only build/packaging surfaces: root `Dockerfile`, new root `aws-cli-pubkey.asc`, `app/pyproject.toml`, `app/uv.lock` (regenerated), `app/Makefile`, `.github/workflows/ci_code.yml`, `README.md` (one line). No application code paths change; no terraform/runtime infra changes (ECS Fargate stays X86_64/LINUX, confirmed no `runtime_platform` override in `terraform/ecs.tf`, so the single-arch AWS CLI installer URL is unambiguous).
- Rollback is a straight revert of the single PR — no data migrations, no schema/API changes. Residual risk is entirely in the image build (multi-stage correctness, AWS CLI installer availability/signature verification, dependency-range re-resolution) and is caught by the build/smoke/test steps above before merge, not at runtime after deploy.
<!-- SECTION:PLAN:END -->
