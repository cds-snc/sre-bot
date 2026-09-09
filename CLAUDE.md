# Project AI Operating Contract

Canonical always-on instructions for **every** AI coding agent on this repo.

Loaded automatically by Claude Code (`CLAUDE.md`) and by GitHub Copilot / VS Code
chat for **all models** (`chat.useClaudeMdFile`). Copilot-only concerns — model
cost tiering, agent routing, `.github/` customization files — live in
`.github/copilot-instructions.md`, which loads *in addition* to this file. Keep
the two disjoint: never restate a rule from here over there.

## Mission

Production-grade Python/FastAPI backend changes: architecture-first decisions,
strict typing, deterministic validation, small reviewable PRs.

Priority order: **safety and correctness → architecture consistency →
testability → cost efficiency → speed.**

## Python Language Baseline (Authoritative)

This repo runs **CPython 3.14** (`app/.python-version`, `requires-python = ">=3.14"`,
mypy `python_version = "3.14"`).

IMPORTANT: The following are **valid, current, non-deprecated** 3.14 syntax. Do
not flag them as errors, "investigate why they parse", or rewrite them to older
equivalents:

- **PEP 758** — `except ValueError, TypeError:` without parentheses (parens still
  required with `as`). This is *not* the removed Python 2 `except E, name:` form.
- **PEP 649/749** — annotations are lazily evaluated; `from __future__ import
  annotations` is unnecessary and itself deprecated; string forward refs are not needed.
- PEP 695/696 type params and `type` aliases, PEP 750 t-strings, PEP 734
  `concurrent.interpreters`, PEP 784 `compression.zstd`.

Full list, removals, and gotchas: **`python-314-baseline` skill**. If a construct
still looks wrong, verify empirically with `cd app && uv run python -c '...'` —
never from training-data recall.

## Architecture Boundaries

- Business logic → `app/packages/<domain>`. Shared platform capabilities →
  `app/infrastructure`. Never put new business logic in `app/infrastructure`.
- `app/modules` is **legacy**: never cite it as an architectural reference.
- `decisions/` holds the authoritative ADRs and is the first source of truth.
  Web research fills gaps; it does not override a current ADR.
- `app/packages/access` is a useful reference, not absolute truth.

### Import boundaries

- Never import concrete implementations from `app/infrastructure/<service>/...`
  in package/domain/route code.
- Resolve infrastructure services via singleton providers in
  `app/infrastructure/services/providers.py`.
- In FastAPI endpoints, consume infrastructure through
  `Annotated[..., Depends(...)]` aliases from `app/infrastructure/services/dependencies.py`.
- Service construction lives in provider layers only.

### Type model boundaries

`Protocol` for behavior contracts · `@dataclass(frozen=True)` for canonical
internal entities · Pydantic `BaseModel` **only** at untrusted I/O boundaries
(HTTP, webhooks, external payloads) · `TypedDict` only when dict semantics are
required. Never default to Pydantic for internal service boundaries.
See `type-model-boundaries` skill.

### Settings

New package domains get `app/packages/<feature>/settings.py`. Do not grow root
settings aggregators for package-owned concerns; pass services the narrowest
slice they need. See `settings-singleton` skill.

### Plugins and startup

Discovery, registration and initialization are startup-driven via lifespan, using
pluggy with `pyproject.toml` entry-points loaded by `pm.load_setuptools_entrypoints`
(`decisions/plugins.md`). Never register at import time; no side-effecting
`__init__.py` bodies. Design new packages plugin-registerable from day one.
See `plugin-registration-lifespan` skill.

## Mandatory Patterns (Every Change)

- **Imports** explicit and minimal, none unused.
- **Config** centralized and typed — no ad-hoc constants.
- **Logging** structured and contextual, no secrets. Prefer
  `structlog.contextvars` middleware binding over threading `request_id` through
  every signature.
- **Async** non-blocking I/O, explicit await boundaries, cancellation-aware.
- **Types** on all public interfaces and internal service boundaries.
- **Errors** mapped explicitly from domain/application boundaries to stable HTTP
  responses.
- **OpenAPI** exactly one tag per router; concise summary/description; explicit
  non-2xx response mapping; described public schema fields.

## Testing

Tests live in `app/tests/` only, named `test_<domain>_<entity>_<action>.py` —
never `test_routes.py`. Route changes need both success and error-mapping
coverage. Test docstrings describe observable behavior, stub strategy and
assertion rationale only — never task ids, sprint labels, plan step numbers or
transitory state. See `testing-standards` skill.

## Verification (Non-Negotiable)

Run after every 3-5 meaningful edits **and** before reporting completion. Always
from `app/`, scoped to project code — never against `.venv` or paths outside the repo.

```bash
cd app && uv run ruff check .                                  # ~0.1s
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'        # ~70s
cd app && uv run pytest tests --ignore=tests/smoke
```

Do **not** run `app/tests/smoke/*` unless explicitly requested with env vars configured.

Report evidence — the command run and its actual output — not an assertion that
it passed. If a gate fails, fix the root cause; never suppress it. Pre-existing
unrelated failures are called out explicitly, not fixed opportunistically.
See `python-quality-gates` skill.

## Task Workflow (Backlog.md)

Work items live under `backlog/tasks/` and are the source of truth for scope,
plans and acceptance criteria.

- Operate tasks **only** through the CLI (`backlog task view/edit/create`).
  Never hand-edit task markdown — the `SECTION`/`AC`/`DOD` markers are CLI-owned.
- A task needs a human-approved implementation plan (`backlog task edit <id> --plan`)
  before implementation. Produce it with `/plan-task <id>`.
- **Single-PR size gate**: a change exceeding ~400 production LOC, ~10 files, two
  subsystems, or mixing mechanical refactor with behavior change MUST be
  decomposed into incremental subtasks before implementation.
- One task per session, one branch, one PR. Check off acceptance criteria one by
  one as each is verified. Agents stop at `In Progress` with notes; **only humans
  move a task to Done.**

See `backlog-task-workflow` and `implementation-planning` skills.

## Working Modes

**Explore → plan → code.** For anything spanning multiple files or unfamiliar
code, research and plan before editing. Skip planning only when you could
describe the diff in one sentence.

- *Architecture mode* — requirements unclear, or introducing/refactoring a
  pattern. Ask clarifying questions first; produce context, alternatives,
  tradeoffs, chosen option, risks, test strategy, acceptance criteria. No code.
- *Implementation mode* — architecture and acceptance criteria are settled.
  TDD: failing tests first, then minimal code, then refactor green.

## Context Discipline

Context is the scarce resource; degraded output is the cost of filling it.

- Delegate output-heavy research and codebase surveys to subagents so file dumps
  stay out of the main session. Keep the main thread for decisions and edits.
- Scope investigations narrowly — never an open-ended "investigate X".
- Prefer `rg` / `rg --files` over `grep`/`find`; read the specific lines you need
  rather than whole files.
- Use web search/fetch for current library and standards guidance when making
  architectural decisions — do not rely on training-data recall for library APIs.

## Git and File-Change Guardrail

- IMPORTANT: Never run git commands unless the user explicitly requests a
  specific git task. The user controls all git operations manually.
- Never modify files outside the scope you were explicitly asked to change.

## Customization Map

| Purpose | Location | Read by |
| --- | --- | --- |
| Always-on contract (this file) | `CLAUDE.md` | Claude Code + Copilot (all models) |
| Copilot model/cost + routing policy | `.github/copilot-instructions.md` | Copilot |
| Skills (knowledge + workflows) | `.claude/skills/<name>/SKILL.md` | Claude Code + Copilot |
| Claude Code subagents | `.claude/agents/*.md` | Claude Code |
| Copilot custom agents | `.github/agents/*.agent.md` | Copilot |
| Path-scoped rules (`applyTo`) | `.github/instructions/*.instructions.md` | Copilot |
| Architecture decision records | `decisions/*.md` | everyone |

**Skill promotion rule**: when a practice is repeatedly validated and stable,
promote it into a skill under `.claude/skills/` rather than growing this file.
Both tools read that directory, so a skill written once serves every model.
