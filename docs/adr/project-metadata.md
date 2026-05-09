---
title: "Project Metadata"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [configuration]
constrained_by: [package-management.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Project Metadata

## Context and Problem Statement

The project's `pyproject.toml` carries the project's metadata in the PEP 621 `[project]` table — its name, version, supported Python range, runtime dependencies, license, and other descriptive fields. PEP 621 is permissive about which fields are used: only `name` is strictly required, and the table can carry as much or as little metadata as the project chooses. The project is a **deployable service** (run as a container), not a library published to PyPI; the metadata that matters for a service is a different subset than the metadata that matters for a library.

The problem this record addresses: **what fields does the project's `[project]` table contain, and how is each field's value sourced?** The decision affects:

1. **Identity and discoverability** — how the project is named, described, and found by contributors and tooling.
2. **Versioning and deployment correlation** — how a deployed instance is correlated back to the source revision that produced it.
3. **License clarity** — how the project's license is declared in a machine-readable, audit-friendly format.
4. **Developer onboarding** — what a new contributor sees when they open `pyproject.toml` to understand the project.
5. **Tool interoperability** — how `uv`, `import-linter`, the build backend, and other tools that read PEP 621 see the project.

**Constraints:**

- The project uses `uv` and PEP 621 in `pyproject.toml`, with PEP 735 dependency groups, per [package-management.md](package-management.md). `dependencies` and `requires-python` are already mandated to live here.
- The project is a service, not a library. There is no PyPI publishing, no wheel distribution, no library consumers.
- The application is launched via `python -m uvicorn …` per [application-lifecycle.md](application-lifecycle.md). There is no console-script entry point that contributors invoke from the shell.
- The project has a `LICENSE` file at the repository root; its content is the source of truth. The metadata declaration must be consistent with that file.

**Non-goals:**

- This record does not define the build backend or `[build-system]` configuration — the package-management decision references the standards (`uv` produces a lockfile and resolves dependencies) but the build-backend choice is out of this metadata ADR's scope.
- This record does not configure tool-specific tables (`[tool.import-linter]`, `[tool.ruff]`, `[tool.pytest]`, etc.) — those are governed by their respective tool ADRs (e.g., [code-quality-tooling.md](code-quality-tooling.md), [import-governance.md](import-governance.md)).
- This record does not enumerate the runtime dependencies themselves — `package-management.md` already mandates that they live in `[project] dependencies`; this record specifies the table's *schema*, not its *contents*.

## Considered Options

**Option 1 — Library-style full metadata.** Populate the full PEP 621 surface: name, version, description, readme, requires-python, license, authors, maintainers, keywords, classifiers, dependencies, optional-dependencies, scripts, entry-points, urls, dynamic version. This is the natural default for a published library.

**Option 2 — Service-shaped minimal metadata.** Populate only the fields that have meaning for a non-published deployable service: name, static version, description, readme, requires-python, license, dependencies, project URLs (repository at minimum). Omit fields that are only meaningful for PyPI-published libraries (keywords, classifiers, optional-dependencies, console-script entry points, authors/maintainers unless policy requires).

**Option 3 — Truly minimal metadata.** Only the strictly required field (`name`). Skip everything else. Functional, but communicates nothing about the project.

## Decision Outcome

**Chosen: Option 2 — service-shaped minimal metadata.**

The `[project]` table contains exactly the metadata that has operational or contributor-onboarding value for a deployable service. Fields whose value is derived from the PyPI publishing model (Trove classifiers, search keywords, optional-dependency extras) are omitted because they encode no information for this project. The result is a `[project]` table that is short, accurate, and free of vestigial declarations a contributor might mistake as load-bearing.

### Required and recommended fields

The `[project]` table contains the following fields, in this order:

- **`name`** — the project's identity, lowercase with hyphens for spaces (PEP 503 normalization). Static; matches the deployed service name.
- **`version`** — a static PEP 440 version string (e.g., `"0.1.0"`). Bumped manually at the maintainer's discretion. The deployed instance's *revision* is correlated to source by an environment-supplied git SHA at runtime — not by the `[project] version` field. (See "Version sourcing" below.)
- **`description`** — a one-line summary of what the service does (≤100 characters). Sufficient for someone opening the file to understand the project's purpose.
- **`readme`** — a reference to `README.md` at the repository root. Conventional and read by tooling.
- **`requires-python`** — a constraint expressing the supported Python range (e.g., `">=3.11,<4"`), per [package-management.md](package-management.md). The exact runtime version is pinned by `.python-version`; this field is the broader compatibility statement.
- **`license`** — an SPDX expression as a string (PEP 639 form, e.g., `license = "MIT"`). The expression matches the content of the `LICENSE` file. Use `license-files = ["LICENSE"]` so any future build artifact includes the license text.
- **`dependencies`** — runtime dependency list, per [package-management.md](package-management.md). The contents are the project's third-party runtime imports; the schema is "list of PEP 508 requirement strings."
- **`[project.urls]`** — at minimum, `repository = "<the repo URL>"`. Other URLs (`issues`, `documentation`) may be added if the project has corresponding public-facing resources. This is the one place a reader can click through from `pyproject.toml` to the project's source of truth.

### Excluded fields and rationale

The following fields are **not** included in `[project]`:

- **`authors` / `maintainers`** — these list package authors for PyPI display. The project is not on PyPI, and ownership is documented in the repository's CODEOWNERS file or equivalent. Including them in `[project]` adds a parallel ownership record that can drift from the source of truth. Omit unless an external policy explicitly requires the metadata.
- **`keywords`** — these drive PyPI search indexing. The project is not on PyPI; keywords have no consumer.
- **`classifiers`** — Trove classifiers (e.g., `"Programming Language :: Python :: 3.11"`) are PyPI-display metadata. The Python version is declared by `requires-python`; duplicating it in classifiers adds drift surface without consumer benefit.
- **`[project.optional-dependencies]`** — these are PEP 621's mechanism for a published package's optional extras (`pip install pkg[extra]`). The project does not publish a distribution; it uses **`[dependency-groups]`** (PEP 735) for development dependencies, per [package-management.md](package-management.md). The two mechanisms must not be mixed.
- **`[project.scripts]` / `[project.entry-points]`** — these declare console scripts and Python entry-point groups. The service is launched by the container's `CMD` invoking `python -m uvicorn app.main:app`, not by a contributor running a project-installed CLI. There is no console script to declare. (If a future management CLI is added — a one-shot admin tool — `[project.scripts]` may be added at that time alongside the CLI's introduction; this record's prohibition is "do not declare entry points that no code provides.")
- **`dynamic`** — this declares which fields are computed by the build backend at packaging time (most commonly `dynamic = ["version"]` to read the version from a git tag or a `__version__` constant). The project's `version` is static; nothing else needs to be dynamic. Omit.

### Version sourcing

The `[project] version` field is a static PEP 440 string. It is **not** derived from a git tag or a runtime constant. Two consequences:

- **Revision identification at runtime is via environment variable**, not via `[project] version`. The container build pipeline supplies `GIT_SHA` (or equivalent) as an environment variable; the application reads it through the `AppSettings` provider per [configuration-ownership.md](configuration-ownership.md) and emits it in logs and on a diagnostic endpoint. Operations look at `GIT_SHA`, not `version`, to identify what is deployed.
- **`version` is bumped manually** when the maintainer decides a meaningful boundary has been crossed (significant feature addition, breaking change in an external interface). The bump is a deliberate act recorded in a commit; it does not happen automatically.

This avoids the build-backend complexity of `setuptools_scm` or `hatch-vcs` (git-tag-driven dynamic versioning), which is designed for libraries that publish discrete releases. A continuously deployed service does not benefit from that machinery.

### Schema example

A representative `[project]` table looks like this:

```toml
[project]
name = "<service-name>"
version = "0.1.0"
description = "<one-line description>"
readme = "README.md"
requires-python = ">=3.11,<4"
license = "<SPDX expression matching LICENSE file>"
license-files = ["LICENSE"]
dependencies = [
  # PEP 508 requirement strings; populated per package-management.md
]

[project.urls]
repository = "<the repo URL>"

[dependency-groups]
dev = [
  # PEP 735 dev dependencies; populated per package-management.md
]
```

No `authors`, no `maintainers`, no `keywords`, no `classifiers`, no `[project.optional-dependencies]`, no `[project.scripts]`, no `dynamic`.

## Consequences

**Positive:**

- The `[project]` table contains only fields whose value matters for the project. A contributor reading it finds nothing vestigial.
- Versioning is a deliberate, low-frequency act tied to source-bump commits, not coupled to deployment cadence. Deployment correlation lives in the runtime environment (`GIT_SHA`), where it belongs operationally.
- License declaration uses the modern SPDX form; tools that read SPDX expressions (compliance scanners, SBOM generators) get a machine-readable answer.
- The boundary between published-library metadata and service metadata is explicit. Contributors who arrive from library projects know to use `[dependency-groups]` (not `[project.optional-dependencies]`) and not to add Trove classifiers.

**Tradeoffs accepted:**

- Static `version` does not auto-correlate with the deployed revision. Operations must look at `GIT_SHA`, not `version`, to know what is running. This is a pattern that has to be communicated; the alternative (dynamic versioning) costs more in build-pipeline complexity.
- Some tools or downstream consumers may expect classifiers/keywords; the project will not provide them. Mitigation: the project is internal; there is no downstream consumer of those fields.

**Risks:**

- A contributor adds a field from a library template (e.g., `[project.optional-dependencies]`) and creates a parallel dev-dependency declaration that drifts from `[dependency-groups]`. Mitigation: code review checks for fields outside this record's allow-list; the schema example above is the canonical reference.
- The `version` is bumped less often than expected, leaving stale numbers. Mitigation: the field is intentionally low-cadence; the operational identity of a deployment is `GIT_SHA`, not `version`. A stale `version` is not a deployment correctness issue.

## Confirmation

Compliance is verified by:

- **Code review.** New fields added to `[project]` must correspond to one of the recommended fields in this record. Excluded fields (classifiers, keywords, optional-dependencies, scripts, dynamic, authors/maintainers) require explicit justification in a PR description and may prompt an ADR amendment.
- **License consistency check.** The `license` SPDX string in `pyproject.toml` matches the content of `LICENSE` at the repository root. A simple CI assertion (or pre-commit hook) compares the two.
- **No `[project.optional-dependencies]`.** A static check (grep or `import-linter` complement) fails if `[project.optional-dependencies]` is present in `pyproject.toml`. Dev dependencies live in `[dependency-groups]` per [package-management.md](package-management.md).

## Source References

1. PEP 621 — Storing Project Metadata in pyproject.toml
   - URL: <https://peps.python.org/pep-0621/>
   - Accessed: 2026-05-08
   - Relevance: Defines the `[project]` table, lists the standard fields, and specifies that only `name` is strictly required; all other fields are optional. Establishes that tools must require `name` to be statically defined and that other fields may be declared `dynamic`. Grounds the field-by-field decisions in this record.

2. PEP 639 — Improving License Clarity with Better Metadata
   - URL: <https://peps.python.org/pep-0639/>
   - Accessed: 2026-05-08
   - Relevance: Specifies the SPDX expression form for the `license` field as a string (e.g., `license = "MIT"`) and the `license-files` field for the LICENSE artifact. Replaces the older `license = { file = "LICENSE" }` table form that PEP 639 deprecates. Grounds the license-declaration rule.

3. PEP 735 — Dependency Groups in pyproject.toml
   - URL: <https://peps.python.org/pep-0735/>
   - Accessed: 2026-05-08
   - Relevance: Distinguishes `[dependency-groups]` (development-only, never published with the distribution) from `[project.optional-dependencies]` (published "extras"). Grounds the rule that the project uses dependency groups for dev dependencies and does not declare optional-dependencies, since it does not publish a distribution.

4. Python Packaging User Guide — pyproject.toml Specification
   - URL: <https://packaging.python.org/en/latest/specifications/pyproject-toml/>
   - Accessed: 2026-05-08
   - Relevance: The official specification of `pyproject.toml`'s structure, restating the PEP 621 field set and clarifying optionality. Confirms that for a non-published project, most metadata fields carry no operational meaning.

5. Python Packaging User Guide — Writing Your pyproject.toml
   - URL: <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>
   - Accessed: 2026-05-08
   - Relevance: The official guidance on constructing a `pyproject.toml`, including the boundary between published-package metadata and project-internal metadata. Confirms that fields like classifiers and keywords are PyPI-display features that have no value for an unpublished project.

6. uv — Project Layout
   - URL: <https://docs.astral.sh/uv/concepts/projects/layout/>
   - Accessed: 2026-05-08
   - Relevance: Documents the minimal `[project]` shape `uv` expects (name and version), confirms PEP 621 alignment, and demonstrates the integration of `[dependency-groups]` for dev dependencies. Grounds the toolchain compatibility of the schema described above.

## Change Log

- 2026-05-08: Created. Establishes a service-shaped (non-library) `[project]` table containing only the fields with operational or onboarding value: `name`, static `version`, `description`, `readme`, `requires-python`, `license` (SPDX), `dependencies`, and `[project.urls] repository`. Excludes `authors`/`maintainers`, `keywords`, `classifiers`, `[project.optional-dependencies]`, `[project.scripts]`, and `dynamic`, with rationale tied to the project not being published to PyPI. Version is static and bumped manually; deployment-revision correlation is by `GIT_SHA` from the environment, not by `[project] version`. License declaration uses the PEP 639 SPDX expression form, matched against the repository's `LICENSE` file.
