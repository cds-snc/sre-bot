---
title: "Package Management"
status: Accepted
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [quality-gates, configuration]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Package Management

## Context and Problem Statement

The project is a Python application with runtime dependencies (FastAPI, Pydantic, vendor SDKs, etc.) and development dependencies (pytest, formatters, linters, type checker). Those dependencies must be declared, resolved, locked, and installed across at least three contexts: a contributor's local development environment, the CI runners that build and test the code on every PR, and the container image the build pipeline produces for deployment.

The problem this record addresses: **which Python package manager and dependency-declaration format does the project use?** The choice has knock-on consequences for:

1. **Reproducibility** — whether two installs produced from the same declaration produce identical artifacts.
2. **Install speed** — how long it takes to materialize the dependency set in CI and in the container build.
3. **Manifest format** — where dependencies are declared and what tooling (`import-linter`, formatters, etc.) co-locates with them.
4. **Dev-vs-prod separation** — how development tools are installed for contributors and CI but excluded from the production image.
5. **Python version pinning** — how the runtime Python version is declared and acquired by the developer and by the build pipeline.

**Constraints:**

- The project uses Python 3.11+ and FastAPI/Uvicorn. Whichever tool is chosen must support modern Python and the standard build backends.
- The codebase already commits to PEP 621 metadata in `pyproject.toml` for tool configuration (the `import-linter` contract file lives there per [import-governance.md](import-governance.md)).
- The deployed artifact is a container image; the package manager must integrate with a multi-stage Dockerfile and produce reproducible layer caches.
- The CI pipeline runs on GitHub Actions; the package manager must integrate with action-level caching keyed on a lockfile.

**Non-goals:**

- This record does not pick the formatter, linter, or type checker — see [code-quality-tooling.md](code-quality-tooling.md).
- This record does not enumerate every entry of the project's PEP 621 `[project]` table — see [project-metadata.md](project-metadata.md).
- This record does not define the container build pipeline itself, only the package manager's role within it — that is an operations concern.

## Considered Options

**Option 1 — `pip` + flat `requirements.txt`.** Dependencies declared in a plain text file; installs performed with `pip install -r requirements.txt`. No lockfile (the pinned `requirements.txt` plays both roles). No dev-vs-prod separation by default.

**Option 2 — `pip` + `pyproject.toml` (PEP 621) + `pip-tools` for locking.** Dependencies declared in `pyproject.toml [project]`; `pip-compile` produces a hashed `requirements.txt` lockfile; `pip-sync` installs.

**Option 3 — Poetry.** Dependencies declared in `pyproject.toml [tool.poetry]` (legacy non-PEP-621 format) or PEP 621 (newer Poetry). `poetry.lock` is the lockfile. Built-in environment management.

**Option 4 — `uv`** (Astral). Dependencies declared in `pyproject.toml [project]` (PEP 621) and `[dependency-groups]` (PEP 735). `uv.lock` is the lockfile. Built-in Python interpreter installation. Native CI and Docker integrations.

## Decision Outcome

**Chosen: Option 4 — `uv`** with PEP 621 dependency declaration, PEP 735 dependency groups, and a committed `uv.lock`.

`uv` is a fast, modern Python package and project manager that supports the file-format standards the project has already committed to (PEP 621 in `pyproject.toml`), produces a deterministic universal lockfile (`uv.lock`), and integrates with both the CI and container build pipelines through documented patterns. Speed and reproducibility are first-order benefits; the format choices align with the rest of the project's `pyproject.toml`-centred tooling.

### Dependency declaration

- **Runtime dependencies** are declared in `pyproject.toml [project]` under `dependencies = […]`. This follows PEP 621 and is the format every modern Python tool reads.
- **Development dependencies** (test, formatter, linter, type checker, pre-commit) are declared in `pyproject.toml [dependency-groups]` under named groups (e.g., `dev`, `test`, `docs`). This follows PEP 735, which standardizes development-only dependency declaration without polluting the built distribution metadata.
- The project does **not** maintain a `requirements.txt` as a primary manifest. If a `requirements.txt` is needed for an external consumer (e.g., a cloud-provider build pipeline that does not understand `pyproject.toml`), it is generated from the lockfile on demand, not edited directly.

### Lockfile

- The project commits a `uv.lock` file at the repository root, alongside `pyproject.toml`.
- `uv.lock` is a universal lockfile: a single file resolves the dependency set for all supported platforms (the project's set of CI and runtime targets).
- `uv.lock` is **never edited by hand**. It is regenerated by `uv lock` (or implicitly by `uv sync` and `uv add`/`uv remove`).
- Lockfile drift is caught at CI: every install in CI uses `uv sync --locked` (or `uv lock --check`), which fails the build if `pyproject.toml` and `uv.lock` are out of sync.

### Python version pinning

- The required Python version range is declared in `pyproject.toml [project]` as `requires-python = ">=3.11,<4"`. This is the PEP 621 standard.
- A `.python-version` file at the repository root pins the exact version used in CI and locally (e.g., `3.11.5`). `uv python install` reads this file and acquires the matching interpreter automatically.
- The container image's base inherits the same version; the `.python-version` file is the single source of truth.

### CI integration

- GitHub Actions workflows use the official `setup-uv` action (`astral-sh/setup-uv@<pinned-version>`). The action installs `uv`, restores the dependency cache keyed on `uv.lock` hash, and exposes `uv` for subsequent steps.
- The standard CI install step is `uv sync --locked` (production + dev dependencies; lockfile must be in sync) or `uv sync --locked --no-dev` (production only, where dev tools are not needed).
- A separate `uv lock --check` step runs early in CI to fail fast if `pyproject.toml` was changed without regenerating `uv.lock`.

### Container build integration

- The Dockerfile uses a multi-stage build that copies `pyproject.toml` and `uv.lock` first, runs `uv sync --locked --no-dev --no-install-project` to install only third-party dependencies into a virtual environment (this layer is cached on lockfile hash), then copies application source and runs `uv sync --locked --no-dev` to install the project itself.
- The production image runs the application via `python -m uvicorn …` against the virtual environment created by `uv`. `uv` itself is not required at runtime (only at build time).
- `--no-dev` excludes the `[dependency-groups] dev` set from the production image.

### Local developer setup

- New contributors run a single command — `uv sync` — to acquire the pinned Python version (via `.python-version`), create a `.venv`, and install all production and development dependencies.
- The `.venv` is gitignored. `uv run <command>` executes commands inside the environment without an explicit activation step.
- Adding a dependency: `uv add <package>` (production) or `uv add --group dev <package>` (development).

### Migration from a `requirements.txt`-based layout

The project currently uses a flat `requirements.txt`. Adopting this decision is a one-time migration:

1. Author `pyproject.toml [project]` with the existing runtime dependencies migrated into `dependencies = […]`.
2. Identify development dependencies (those used only in tests, linting, formatting) and move them under `[dependency-groups] dev = […]`.
3. Run `uv lock` to generate `uv.lock`. Commit `pyproject.toml`, `uv.lock`, and `.python-version`.
4. Update the Dockerfile to use the multi-stage `uv sync --locked` pattern.
5. Update the CI workflow to use `astral-sh/setup-uv` and `uv sync --locked`.
6. Remove `requirements.txt` (and `requirements-dev.txt` if present). Update README onboarding steps to reference `uv sync`.

## Consequences

**Positive:**

- A single committed lockfile produces deterministic installs across local, CI, and container environments.
- Install speed is materially faster than the alternatives evaluated, both at cold install (no cache) and at cached install. Faster CI feedback and faster container builds compound across the workflow.
- The project's tool configuration (`import-linter`, future formatter/linter config) and dependency declaration co-locate in `pyproject.toml`. Contributors look in one place.
- Adding, removing, or updating a dependency is a single `uv add`/`uv remove`/`uv lock --upgrade-package` command; the lockfile is regenerated automatically.
- `uv` manages the Python interpreter version itself, removing the need for an external `pyenv` (or equivalent) on developer machines.

**Tradeoffs accepted:**

- A migration from `requirements.txt` to `pyproject.toml` + `uv.lock` is required. The migration is mechanical and one-time; thereafter, the cost is paid in saved install time on every CI run and every container build.
- `uv` is a relatively newer tool than `pip` or `poetry`. The project takes on a dependency on Astral's continued maintenance. Mitigation: `uv.lock` is human-readable TOML and `pyproject.toml` is a standard format; a future migration to a different tool that reads PEP 621 is mechanical, not disruptive.
- Contributors unfamiliar with `uv` need to learn its commands. The surface area is small (`sync`, `add`, `remove`, `lock`, `run`); the learning cost is bounded.

**Risks:**

- A contributor edits `pyproject.toml` without running `uv lock`, leaving `uv.lock` stale. Mitigation: CI's `uv lock --check` step fails the build before merge.
- The Dockerfile copies `pyproject.toml` but forgets to copy `uv.lock`, breaking the cached install layer. Mitigation: code review; the Dockerfile is short and the dependency layer is the obvious caching unit.

## Confirmation

Compliance is verified by:

- **Repository contents.** `pyproject.toml` and `uv.lock` exist at the repository root. `requirements.txt` does not exist (or is auto-generated and clearly marked as such). `.python-version` exists at the root.
- **CI step.** A `uv lock --check` step runs early in the workflow and fails on lockfile drift. The dependency-installation step is `uv sync --locked …`, never `pip install`.
- **Dockerfile.** The Dockerfile uses `uv sync --locked --no-dev` (or equivalent) to install dependencies; no `pip install -r requirements.txt` line remains.
- **Code review.** New dependencies are added through `uv add`, not by manually editing `uv.lock`. The lockfile is treated as generated artifact (committed, but not authored).

## Source References

1. uv — Official Documentation
   - URL: <https://docs.astral.sh/uv/>
   - Accessed: 2026-05-08
   - Relevance: Documents `uv` as a Python package and project manager that resolves, locks, and installs dependencies, manages Python interpreter versions, and integrates with PEP 621 / PEP 735 metadata. Establishes the speed claims and the project-management commands the rules above use.

2. uv — Lockfile Concept
   - URL: <https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile>
   - Accessed: 2026-05-08
   - Relevance: Documents `uv.lock` as a universal, human-readable, committed lockfile that resolves dependencies for all supported platforms. Grounds the rule that `uv.lock` is committed to the repository and never edited by hand.

3. uv — Docker Integration Guide
   - URL: <https://docs.astral.sh/uv/guides/integration/docker/>
   - Accessed: 2026-05-08
   - Relevance: Documents the multi-stage Dockerfile pattern that copies `pyproject.toml` and `uv.lock` first, runs `uv sync --locked --no-install-project` to materialize the dependency layer cache, and then installs the project. Grounds the container build integration rule.

4. uv — GitHub Actions Integration Guide
   - URL: <https://docs.astral.sh/uv/guides/integration/github/>
   - Accessed: 2026-05-08
   - Relevance: Documents the `astral-sh/setup-uv` GitHub Action, action-level caching keyed on `uv.lock` hash, and `.python-version` file handling. Grounds the CI integration rule.

5. PEP 621 — Project Metadata
   - URL: <https://peps.python.org/pep-0621/>
   - Accessed: 2026-05-08
   - Relevance: Defines the `pyproject.toml [project]` table as the standard location for project name, version, Python version constraint, dependencies, and entry points. Grounds the runtime-dependency declaration format.

6. PEP 735 — Dependency Groups in pyproject.toml
   - URL: <https://peps.python.org/pep-0735/>
   - Accessed: 2026-05-08
   - Relevance: Defines the `pyproject.toml [dependency-groups]` table for named development-only dependency sets that are not published with the distribution. Grounds the dev-vs-prod separation rule.

7. PEP 517 — A Build-System Independent Format for Source Trees
   - URL: <https://peps.python.org/pep-0517/>
   - Accessed: 2026-05-08
   - Relevance: Establishes `pyproject.toml` as the configuration file for the project's build system and the entry point for tools that operate on a Python project. Grounds the choice to centralize project tooling configuration in `pyproject.toml`.

## Change Log

- 2026-05-08: Created. Selects `uv` as the project's package and dependency manager. Establishes PEP 621 `[project]` declarations for runtime dependencies, PEP 735 `[dependency-groups]` for development dependencies, a committed `uv.lock` as the universal lockfile, `.python-version` plus `requires-python` for Python version pinning, the `astral-sh/setup-uv` action for CI integration, and a multi-stage Dockerfile pattern for cached dependency installation in container builds. Migration from `requirements.txt` is one-time and mechanical; thereafter the canonical install command is `uv sync --locked`.
