# Project AI Operating Contract

## Mission

Produce production-grade Python/FastAPI backend changes with architecture-first decision making, strict typing, deterministic validation, and low premium request waste.

## Priority Order

1. Safety and correctness
2. Architecture consistency
3. Testability and maintainability
4. Cost-efficient Copilot usage
5. Speed

## Product and Architecture Constraints

- Runtime target: Python 3.12+.
- Framework: FastAPI.
- Focus: API/backend only.
- Shared platform capabilities belong in `app/infrastructure`.
- Business logic belongs in `app/packages/<domain>`.
- Do not place new business logic in `app/infrastructure`.
- Treat `app/modules` as legacy and do not use it as an architectural reference.
- Prefer architecture references from `app/infrastructure` and `app/packages`.
- `app/packages/access` is a useful reference package but not a source of absolute truth.
- Prefer partitioned settings for new package domains in `app/packages/<feature>/settings.py`.
- Avoid growing root settings aggregators for new package-owned concerns.
- Services should receive the narrowest settings slice needed, not broad root settings objects.

## Model Boundary Rules

- Use `Protocol` for behavior/service contracts.
- Use `@dataclass(frozen=True)` for canonical internal entities and shared internal data.
- Use Pydantic `BaseModel` at untrusted I/O boundaries (HTTP, webhook, external payload parsing).
- Use `TypedDict` only when dictionary semantics are explicitly required.
- Do not default to Pydantic models for internal service boundaries.

## Plugin and Startup Rules

- Package discovery/registration/loading/initialization must be startup-driven via lifespan.
- Use pluggy-based registration for package capabilities.
- Register packages via `pyproject.toml` entry-points loaded at startup (`pm.load_setuptools_entrypoints`), per `decisions/plugins.md` — declarative, reviewed registration, not implicit filesystem discovery.
- Never perform plugin registration at import time (no side-effecting code in `__init__.py` bodies).
- Design all new packages to be plugin-registerable from day one.

## Working Modes

### Architecture Mode

Use when requirements are unclear, when introducing/refactoring patterns, or before major implementation.

Required behavior:

- Architect first, then implement.
- Research best practices in isolation from current code.
- Ask clarifying questions before proposing implementation.
- Produce explicit decisions: context, alternatives, tradeoffs, chosen option, risks, test strategy.
- Define acceptance criteria before coding begins.

### Implementation Mode

Use when architecture and acceptance criteria are clear.

Required behavior:

- Follow TDD loop: write or update failing tests first, implement, then iterate to green.
- Keep changes scoped to the agreed architecture.
- Maintain strict typing and predictable async behavior.
- Run validations after every 3-5 meaningful changes and before completion.
- Prefer reusable prompt files for recurring workflows under `.github/prompts/*.prompt.md`.

## Task Workflow (Backlog.md)

Work items live as Backlog.md tasks under `backlog/tasks/` and are the source of truth for scope, plans, and acceptance criteria.

- Operate tasks only through the backlog CLI (`backlog task view/edit/create`); never hand-edit task markdown files. See the `backlog-task-workflow` skill and `backlog instructions overview`.
- Before implementing a backlog task, it must have a human-approved implementation plan written into the task (`backlog task edit <id> --plan`). Use the `task-planner` agent (`/plan-task <id>`) to produce it.
- Single-PR size gate: if a task's change is too large for one reviewable PR (~400 production LOC / ~10 files / multiple subsystems / mixed refactor+behavior), it must be decomposed into smaller, safer, incremental subtasks (`backlog task create ... --dep --parent`) before implementation. See the `implementation-planning` skill. This is mandatory so the dev team can properly review every change.
- One task per session, one branch, one PR. Agents check acceptance criteria one by one as verified and stop at In Progress with notes; humans move tasks to Done.

## Testing Placement and Naming

- Place tests in `app/tests/` only.
- Use feature-prefix names (for example, `test_groups_routes.py`, `test_identity_resolver.py`).
- Avoid ambiguous test file names such as `test_routes.py`.
- For FastAPI route changes, include success and error-mapping path coverage.

## Request Context and Logging

- Prefer `structlog.contextvars` middleware binding for request context propagation.
- Avoid threading `request_id` through every signature unless crossing boundaries that require explicit values.

## Dependency Import Boundaries

- Do not import concrete infrastructure service implementations directly from `app/infrastructure/<service>/...` in package/domain/route code.
- Resolve infrastructure services via singleton provider functions in `app/infrastructure/services/providers.py`.
- For FastAPI endpoints, consume infrastructure dependencies through `Annotated[..., Depends(...)]` aliases from `app/infrastructure/services/dependencies.py` (or re-exported `infrastructure.services` symbols), not by importing concrete classes.
- Keep service construction in provider layers only; route and business modules must not instantiate infrastructure clients/services directly.

## OpenAPI and Route Metadata

- Router declarations should include exactly one tag.
- Route handlers should include concise summary/description and explicit response mapping.
- Public schema fields should include clear field descriptions.

## Mandatory Generation Patterns (Every Change)

- Imports: explicit, minimal, no unused imports.
- Settings/config: centralized, typed, no ad-hoc constants scattered in code.
- Logging: structured, contextual, no sensitive data leakage.
- Async: non-blocking paths for I/O, explicit await boundaries, cancellation-aware patterns.
- Types: type hints on public interfaces and internal service boundaries.
- Errors: explicit domain/application boundaries and predictable API error mapping.

## Tooling Policy

- Use web search/fetch tooling for up-to-date best practices and documentation when making architectural or library decisions.
- Use Bash for fast repository analysis; prefer `rg` and `rg --files`, fallback to `grep/find` if needed.
- Use subagents for research/investigation/output-heavy tasks; keep main session focused on decisions and implementation.

## Validation Policy

Run these checks regularly (after each 3-5 edits and before completion):

- `cd app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'`
- `cd app && uv run ruff check .`
- `cd app && uv run pytest tests --ignore=tests/smoke`

Always run validation from `app/` and scope checks to project code only. Do not run quality gates against repository-external paths or virtual environment contents.

Do not run `app/tests/smoke/*` unless explicitly requested and required environment variables are configured.

If a check fails, fix root causes before proceeding.

## Git and File-Change Guardrail

- Never run git commands unless the user explicitly requests a specific git task.
- Never modify files unless explicitly asked for the task.
- User controls all git operations manually.

## Customization Paths

- Always-on workspace instructions: `.github/copilot-instructions.md`.
- Scoped instructions: `.github/instructions/*.instructions.md` with `applyTo` globs.
- Skills: `.github/skills/<skill-name>/SKILL.md` where frontmatter `name` matches folder name in kebab-case.
- Custom agents: `.github/agents/*.agent.md`.
- Prompt files: `.github/prompts/*.prompt.md`.
- Hooks: `.github/hooks/*.json`.
- Workspace MCP configuration: `.vscode/mcp.json`.

## Skill Promotion Rule

When a best practice is repeatedly validated and stable, create/update a dedicated skill for it and reference that skill from architecture/implementation workflows.
