---
status: Accepted
date: 2026-07-06
applies: target
scope: Packaging, Python version, lint/format/types, import enforcement, CI gates.
---

# Toolchain

## Context

Current state: Python 3.11 in CI, 3.12 in the venv, **3.14 in the Docker image**; the Dockerfile ignores `uv.lock`; the formatter is black while ruff lints three rule families; mypy soft-fails through `|| true`; dev deps sit in the construct the metadata rules ban; stale references to a deleted `core` package linger in hatch and Makefile config. Every gap below is config, not code.

## Decision

**Python:** one version — **3.14** — pinned in `.python-version`, CI, and the Docker base image. The image already runs 3.14 in production, every runtime dep (FastAPI, pydantic v2, slack-bolt, boto3) officially supports it, and 3.13 leaves its bugfix phase in Oct 2026 — so converging CI/venv *up* to 3.14 is the change that touches nothing shipped. `requires-python = ">=3.13"` (no upper bound). Nothing tests on a different interpreter than production runs.

**Packaging:** `uv` end to end. Loose constraints in `[project] dependencies` (exactness lives in `uv.lock`); dev tools in PEP 735 `[dependency-groups]`; `uv lock --check` and `uv sync --locked` in CI; the Dockerfile is multi-stage and installs with `uv sync --locked --no-dev`. The repo keeps its **flat import layout** (`infrastructure`, `integrations`, `packages` as top-level names with `app/` as the working root) — an installed `app.`-rooted package is deliberately deferred; the cost (generic top-level names) is accepted and revisited only if the app ever ships as a library. `awscli` leaves runtime dependencies; stale `core` references are deleted.

**Format & lint:** ruff for both (black removed). Rule families: `E,F,W,I,B,UP,C4,SIM` + `S` (bandit-via-ruff — no separate bandit gate; one tool, one suppression syntax). Line length 100–130 per current code; `I` makes import order enforced for the first time.

**Types:** mypy with a **ratchet, not a strict default**: loose global baseline (`check_untyped_defs = true`), plus a growing per-package strict list starting with `packages/` and `infrastructure/` — new code is strict, legacy earns strictness as it's touched. The strict list only grows. (Re-evaluate Astral's `ty` when it reaches 1.0; the ratchet config transfers.)

**Import contracts:** import-linter (`lint-imports`) in CI with the four contracts from [layers.md](layers.md)/[feature-packages.md](feature-packages.md), written against the flat names via `root_packages`. The ratchet mechanism: existing violations are enumerated in per-contract `ignore_imports` with `unmatched_ignore_imports_alerting` on, so the list only shrinks and stale entries are flagged. A deprecated-import guardrail (a freeze baseline that only ratchets down) plus a client-usage-matrix report guard the client-layer migration, and are retired once their baselines empty.

**CI gates:** every quality command is blocking — `|| true` is banned as a pattern. pre-commit (or `prek`, its config-compatible Rust successor) runs the same hooks locally; CI runs the hooks over all files + the test job.

**Project metadata:** `[project]` carries name, static version, description, readme, `license`/`license-files` (SPDX), requires-python, dependencies, `[project.urls]`. Runtime revision identity is `GIT_SHA` env, not version bumps.

## Consequences

- Reproducibility becomes real at the one boundary that matters (the shipped image).
- The ratchet direction (loose → strict per package) fits a codebase with a large legacy tree; a strict default with a giant exemption list would have been the same policy with worse ergonomics.
- Dropping black/bandit-standalone removes two tool configs; ruff's equivalents are close enough.

## Checks

- CI: `uv lock --check`, `uv sync --locked`, `pre-commit run --all-files`, import-linter, mypy (blocking), pytest.
- grep: no `|| true` in Makefile/workflows; no `black` in dependencies; single Python version string across `.python-version`/CI/Dockerfile.
- Dockerfile: multi-stage, `--locked --no-dev`, non-editable install.

## Migration

Ticket: toolchain convergence (Phase 2). Tolerated until closed: black formatting, soft-fail mypy, 3.11 CI / 3.12 venv lagging the 3.14 image, optional-dependencies dev group.
