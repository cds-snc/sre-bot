---
title: "Code Quality Tooling"
status: Accepted
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [quality-gates]
constrained_by: [package-management.md, project-metadata.md, import-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Code Quality Tooling

## Context and Problem Statement

The project's static-quality concerns split cleanly into four orthogonal axes that every Python codebase must answer for: **formatting** (mechanical layout of source code), **linting** (style rules and small correctness checks), **type checking** (static verification of type annotations against `typing.Protocol` boundaries and value-object shapes), and **security analysis** (AST-based detection of common vulnerable patterns). Each axis can be addressed by a different combination of tools; the choices interact (one configuration file vs. four, one CI step vs. four, one set of pre-commit hooks vs. several).

The problem this record addresses: **which tools cover those four axes, where do they configure, and how do they run as mandatory gates in local development and in CI?** The answer determines:

1. How many separate tools contributors must install, configure, and learn.
2. Where each tool's configuration lives (single `pyproject.toml` vs. multiple dotfiles), which directly affects whether a contributor can find every project rule in one place.
3. Whether quality checks block PRs (mandatory gate) or are advisory (soft-fail).
4. Whether the same set of checks runs locally before commit and in CI on every PR (parity), or whether contributors learn about violations only after pushing.

**Constraints:**

- Dependencies and tool configuration co-locate in `pyproject.toml` per the project's package management decision; tools that cannot configure there are at a disadvantage.
- The project metadata table in `pyproject.toml` is intentionally minimal — quality-tooling configuration adds named `[tool.*]` sections rather than expanding `[project]`.
- Static enforcement of import-graph contracts is delegated to a separate, dedicated tool (already decided); this record does not duplicate or replace that enforcement.
- The CI pipeline runs on GitHub Actions; tools must have either a published GitHub Action or work as a plain CLI installed via the project's package manager.

**Non-goals:**

- This record does not pick the test runner or testing standards — that is a separate concern.
- This record does not enumerate every linter rule or every type-check option enabled; it specifies the *tools*, the *config location*, and the *enforcement policy*. The detailed rule sets evolve through normal PR review.
- This record does not pick the dependency-vulnerability scanner (e.g., `pip-audit`, Dependabot). That is an operations concern.
- This record does not duplicate the import-graph contract enforcement — that lives in its own ADR and uses a dedicated tool.

## Considered Options

**Option 1 — Per-axis classic stack (`black` + `flake8` + `isort` + `mypy` + `bandit`).** Each axis is owned by a separate single-purpose tool. Each tool has its own configuration (potentially across several files). Five tools to install, configure, version-pin, and run.

**Option 2 — Consolidated stack (`ruff` for format + lint + import sort, `mypy` for typing, `bandit` for security).** A single Rust-implemented tool covers formatting, linting, and import sorting; a separate type checker covers typing; a separate security scanner covers security analysis. Fewer tools, faster execution, single `pyproject.toml` configuration block per concern.

**Option 3 — Consolidated stack with `pyright` instead of `mypy`.** As Option 2, but the type checker is `pyright` (Microsoft's TypeScript-style type checker for Python). Faster than `mypy` on large codebases; integrates with VS Code natively; configured in `pyproject.toml [tool.pyright]`.

**Option 4 — Run tools only in CI (no local pre-commit framework).** Same tool selection as any of the above, but contributors discover violations only when CI runs after push. No `.pre-commit-config.yaml`, no local hooks.

## Decision Outcome

**Chosen: Option 2 — `ruff` (format + lint + import sort) + `mypy` (type checking) + `bandit` (security) — orchestrated by `pre-commit` locally and run as mandatory gates in CI.**

The selection collapses the format/lint/import-sort axes into a single tool, keeps the established type checker, and introduces a local hook framework so the same checks gate both `git commit` and CI. Every tool configures in `pyproject.toml` (alongside dependencies and project metadata), and every check is a blocking gate — no soft-fail.

### Tool selection per axis

| Axis | Tool | Rationale |
| --- | --- | --- |
| Formatter | `ruff format` | Black-compatible output; replaces a separate formatter binary |
| Linter | `ruff check` | Replaces `flake8` plus its plugin ecosystem; native re-implementations in Rust |
| Import sorter | `ruff check --select I` | Replaces `isort`; same tool, same config file |
| Type checker | `mypy` | Established static type checker; integrates with the Protocol-based contracts the codebase already uses |
| Security analysis | `bandit` | AST-based scanner for common Python security anti-patterns; runs against `app/` only |
| Hook orchestration | `pre-commit` | Manages local git hooks and runs the same hooks in CI for parity |

`pyright` was considered for Option 3. It is faster on large codebases and has native VS Code integration, but the codebase already runs `mypy` and the cost of switching outweighs the benefit at this size; if the project's typing surface grows past where `mypy` performance becomes a bottleneck, the switch is mechanical (the type annotations themselves are tool-agnostic).

### Configuration location

All tool configuration lives in `pyproject.toml` under named `[tool.*]` sections:

- `[tool.ruff]` — global Ruff settings (line length, target Python version, exclude paths).
- `[tool.ruff.lint]` — selected rule sets (`select = ["E", "F", "I", "B", "UP", "S"]` and the like; the actual rule selection is defined and tuned in the config file, not in this ADR).
- `[tool.ruff.format]` — formatter overrides if any (e.g., quote style); defaults are accepted unless a project-wide reason justifies divergence.
- `[tool.mypy]` — global mypy settings, including `strict = true` as the project default.
- `[[tool.mypy.overrides]]` — per-module relaxations for legacy modules during incremental adoption; each override carries a tracking comment naming the module and the deadline by which the relaxation is removed.
- `[tool.bandit]` — Bandit configuration (severity threshold, file exclusions). Bandit is invoked with `-c pyproject.toml` because it does not auto-discover its config in `pyproject.toml`.

No tool has a sidecar config file (`.flake8`, `setup.cfg`, `mypy.ini`, `.bandit`). One file is the source of truth for every static-quality rule the project enforces.

### Local enforcement: `pre-commit` framework

A `.pre-commit-config.yaml` at the repository root declares the hooks. New contributors run `uv run pre-commit install` once after `uv sync`; thereafter, `git commit` runs the hooks against staged files automatically. The hooks are:

1. `ruff-check` (with `--fix`) — lint with autofix.
2. `ruff-format` — format.
3. `mypy` — type-check the application source tree.
4. `bandit` — security analysis on the application source tree.
5. Basic file-hygiene hooks from `pre-commit-hooks` (trailing whitespace, end-of-file fixer, large-file check, merge-conflict marker check). These cost nothing and prevent recurring review-time noise.

Hook order matters when `--fix` is enabled: `ruff-check` runs before `ruff-format` so that lint autofixes pass through the formatter rather than the other way around.

### CI enforcement: same hooks, mandatory

The CI workflow runs `uv run pre-commit run --all-files` as a single job step. Running the same hook set against the full repository (not just staged files) guarantees that:

- A contributor who skips local hooks (`git commit --no-verify`) is caught at CI.
- The CI environment runs identical tool versions to local environments because both pin to the versions declared in `.pre-commit-config.yaml` and `pyproject.toml`.
- Adding a new hook is a single edit in one file and takes effect locally and in CI on the same PR.

Every hook is a blocking gate: a non-zero exit code fails the CI step. The previous arrangement of soft-failing the type checker (`mypy ... || true`) is not carried forward — soft-fail is a tooling anti-pattern (a tool is run but its result is ignored). Where strictness cannot be applied uniformly across the codebase (legacy modules during a typing migration), the relaxation is encoded in `[[tool.mypy.overrides]]` so the relaxation is visible, named, and reviewable, not hidden behind `|| true`.

### Mypy strictness policy

The project default is `strict = true` in `[tool.mypy]`. Strict mode enables the full set of mypy checks (untyped-defs, untyped-calls, optional, return-any, etc.) so that the codebase's `typing.Protocol` contracts and Pydantic boundaries are statically verified end-to-end. Modules that are not yet strict-clean are exempted explicitly in `[[tool.mypy.overrides]]` with a tracking comment; the exemption list shrinks toward zero, never grows by default. New code is written strict-clean from day one.

### Tool-version management

All quality tools are declared in `pyproject.toml [dependency-groups] dev`. The lockfile pins exact versions, so every contributor and every CI run resolves to the same `ruff`, `mypy`, `bandit`, and `pre-commit` versions. Tool upgrades are normal dependency updates: `uv lock --upgrade-package ruff` produces a lockfile change that goes through PR review.

The `.pre-commit-config.yaml` `rev` fields for hook repositories are pinned to the same versions as the corresponding `dev`-group entries; they are bumped together. (This avoids drift between the version `pre-commit` runs and the version installed in the developer's `uv` environment for direct CLI use.)

## Consequences

**Positive:**

- Contributors install one set of dev dependencies and find every static-quality rule in one configuration file.
- Local hooks and CI run the same tools against the same configuration. A passing local commit is a strong signal of a passing CI run.
- The format / lint / import-sort consolidation removes three single-purpose tools and three separate configuration sections; the cumulative reduction in cognitive surface for new contributors is real.
- Mandatory gates with no soft-fail mean the CI signal is honest: a green build is a build that passes every check, not "passes some and silently ignores others."
- Tool versions are lockfile-pinned; an upgrade is a deliberate PR change, not a surprise.

**Tradeoffs accepted:**

- A migration from the prior format/lint stack (`black` + `flake8`) to `ruff` is required. Format output may differ on a small number of edge cases; the migration is one-time and produces a single large diff that is reviewed and merged before tightening becomes the steady state.
- Strict mypy on the entire application surface is an aspiration; modules not yet strict-clean carry overrides. Each override is debt that must be paid down, tracked in the override block itself.
- `bandit` runs as a hook on every commit, which adds a few hundred milliseconds locally. The cost is small and bounded; the benefit is that high-severity findings cannot be merged unnoticed.

**Risks:**

- A contributor uses `git commit --no-verify` and pushes code that fails one of the hooks, costing a CI cycle to find a violation that should have been caught locally. Mitigation: CI runs the identical hook set; the violation is caught before merge.
- The set of `mypy.overrides` becomes a dumping ground rather than a tracked debt list. Mitigation: each override entry includes a comment naming the module and the deadline (or condition) for removal; review of the overrides block is part of normal PR review.
- A future tool change (e.g., switching `mypy` to `pyright`) is held back because the existing override list is large. Mitigation: the override entries live in `pyproject.toml`, not in tool-specific files, so re-evaluating them under a new tool is a plain text-search operation.

## Confirmation

Compliance is verified by:

- **Repository contents.** `pyproject.toml` contains `[tool.ruff]`, `[tool.mypy]`, and `[tool.bandit]` sections. `.pre-commit-config.yaml` exists at the root and references the version-pinned tools. No `.flake8`, `setup.cfg [flake8]`, `mypy.ini`, or `.bandit` file exists.
- **CI step.** A single CI step runs `uv run pre-commit run --all-files`. The step is a required check on the protected branch. There is no `|| true` on any quality command.
- **Dev-group dependency declaration.** `ruff`, `mypy`, `bandit`, and `pre-commit` appear in `[dependency-groups] dev` with the lockfile pinning their versions.
- **Code review.** A PR that adds a new `[[tool.mypy.overrides]]` entry must justify the override (legacy module under migration, third-party stub gap, etc.) and name the condition under which the override will be removed. PRs that remove overrides are encouraged.

## Source References

1. Ruff — Official Documentation (Astral)
   - URL: <https://docs.astral.sh/ruff/>
   - Accessed: 2026-05-08
   - Relevance: Documents Ruff as a single Rust-implemented tool that replaces `flake8` (with plugins), `black`, `isort`, and several other format/lint tools, configures in `pyproject.toml`, and is materially faster than the tools it replaces. Grounds the consolidation choice in Option 2.

2. Ruff Formatter — Black Compatibility
   - URL: <https://docs.astral.sh/ruff/formatter/>
   - Accessed: 2026-05-08
   - Relevance: Documents that `ruff format` is designed as a drop-in replacement for `black`, with > 99.9% line-identical output on large Black-formatted projects. Grounds the formatter choice and the migration claim.

3. Ruff Integrations — Pre-commit and GitHub Actions
   - URL: <https://docs.astral.sh/ruff/integrations/>
   - Accessed: 2026-05-08
   - Relevance: Documents the canonical `astral-sh/ruff-pre-commit` configuration and the rule that `ruff-check` must run before `ruff-format` when `--fix` is enabled. Grounds the `.pre-commit-config.yaml` hook ordering rule.

4. mypy — Documentation Index
   - URL: <https://mypy.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents `mypy` as a static type checker for Python that supports `pyproject.toml [tool.mypy]` configuration, gradual typing through per-module options, and a strict mode that enables a broad set of additional checks. Grounds the `mypy` selection and the per-module override mechanism.

5. mypy — Getting Started
   - URL: <https://mypy.readthedocs.io/en/stable/getting_started.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `--strict` flag and its claim that strict mode catches type-related runtime errors statically except where deliberately circumvented. Grounds the project default of `strict = true` with explicit overrides for incremental adoption.

6. Bandit — Configuration Documentation
   - URL: <https://bandit.readthedocs.io/en/latest/config.html>
   - Accessed: 2026-05-08
   - Relevance: Documents that Bandit configuration in `pyproject.toml [tool.bandit]` requires explicit `-c pyproject.toml` invocation (Bandit does not auto-discover the section). Grounds the rule that Bandit runs with `-c pyproject.toml -r app/`.

7. pre-commit — Framework Documentation
   - URL: <https://pre-commit.com/>
   - Accessed: 2026-05-08
   - Relevance: Documents `pre-commit` as a multi-language hook orchestration framework that reads `.pre-commit-config.yaml`, installs git hooks via `pre-commit install`, and runs the same hook set in CI via `pre-commit run --all-files`. Grounds the local-hook / CI-parity rule.

8. pyright — Repository (Microsoft)
   - URL: <https://github.com/microsoft/pyright>
   - Accessed: 2026-05-08
   - Relevance: Documents `pyright` as a full-featured, standards-based static type checker for Python optimized for large codebases. Cited as the alternative considered in Option 3 and as a documented future-migration target if `mypy` performance becomes a bottleneck.

## Change Log

- 2026-05-08: Created. Selects `ruff` (format + lint + import sort), `mypy` with `strict = true`, and `bandit` as the project's static-quality tool set, with `pre-commit` orchestrating identical local and CI hook runs. All configuration co-locates in `pyproject.toml`. Every hook is a blocking gate; soft-fail (`|| true`) is not used. Per-module mypy relaxations are encoded as named `[[tool.mypy.overrides]]` entries with tracking comments, never hidden behind ignored exit codes. Tool versions are lockfile-pinned and the `.pre-commit-config.yaml` `rev` fields move together with the `dev` dependency-group versions.
