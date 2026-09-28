---
id: TASK-104
title: >-
  Align CLAUDE.md, the Copilot instructions and the skills with the six-layer
  plugin architecture
status: To Do
assignee: []
created_date: '2026-09-24 19:57'
updated_date: '2026-09-28 15:03'
labels:
  - plugin-architecture
  - docs
milestone: m-7
dependencies: []
references:
  - decisions/plugin-architecture.md
  - decisions/dependency-injection.md
  - decisions/plugins.md
  - CLAUDE.md
priority: high
type: docs
ordinal: 244000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md (Accepted 2026-09-24) replaced the three-tier model with six layers: server, features, capabilities, infrastructure, integrations and contracts. Its Migration section asks for this ticket first: every agent reads CLAUDE.md on every session, so a stale contract there steers new code into the old shape.

Verified drift (2026-09-24):
- CLAUDE.md "Architecture Boundaries" and "Import boundaries" describe packages -> infrastructure -> integrations and tell agents to resolve services through app/infrastructure/services/providers.py and consume them through Depends aliases in app/infrastructure/services/dependencies.py. That directory does not exist. The target is the svcs registry in app/server/ (decisions/dependency-injection.md).
- CLAUDE.md "Plugins and startup" does not mention per-environment enablement or extension points (decisions/plugins.md).
- .github/copilot-instructions.md, .github/instructions/*.instructions.md, .github/agents/*.agent.md, .claude/agents/*.md and the skills that restate architecture (plugin-registration-lifespan, settings-singleton, fastapi-api-patterns, testing-standards, type-model-boundaries, implementation-planning, architecture-review, feature-architecture, groom-backlog, plan-task) may cite the deleted records layers.md, capability-packages.md or events.md, or the old provider pattern.

Scope: documentation only. State the target rules and say plainly what is still tolerated today, by linking the record's Migration section rather than copying its table. No code changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CLAUDE.md states the six layers and their import rules and cites decisions/plugin-architecture.md; it no longer references app/infrastructure/services/ or the deleted records layers.md, capability-packages.md and events.md
- [ ] #2 grep over CLAUDE.md, .github/ and .claude/ finds no reference to the deleted records or to infrastructure/services/providers.py or dependencies.py
- [ ] #3 Each skill or agent file that restates an architecture rule distinguishes the target from what is tolerated today and links the owning decision record instead of copying its table
- [ ] #4 CLAUDE.md and .github/copilot-instructions.md stay disjoint, per CLAUDE.md's own rule
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope

Docs-only. Rewrite the architecture guidance in CLAUDE.md and correct every downstream
restatement in .github/ and .claude/ so they match decisions/plugin-architecture.md's six
layers (server > features > capabilities > infrastructure > integrations > contracts),
while staying true about today's transitional main (app/packages/, app/modules/ still exist;
app/contracts/ arrives with TASK-106; the svcs registry with TASK-109; entry-point loading
with TASK-110; per-environment enablement is not built). Every edit states the target,
states what's tolerated today, and links the owning decision record instead of copying its
table (task Scope line, AC3).

No code changes. No task other than TASK-104 is touched.

## Files touched (13) and ordering

Commit/review order inside this one PR (small, mechanical, reviewable top to bottom):

1. CLAUDE.md
2. .github/instructions/packages-python.instructions.md
3. .github/instructions/infrastructure-python.instructions.md
4. .github/instructions/tests-python.instructions.md
5. .github/agents/codebase-researcher.agent.md
6. .github/agents/implementation.agent.md
7. .claude/agents/architecture.md
8. .claude/agents/codebase-researcher.md
9. .claude/agents/feature-architecture.md
10. .claude/skills/feature-architecture/SKILL.md
11. .claude/skills/settings-singleton/SKILL.md
12. .claude/skills/testing-standards/SKILL.md
13. .claude/skills/plugin-registration-lifespan/SKILL.md (minor addition only)

Confirmed clean (codebase-researcher sweep + targeted greps), no edit: .github/copilot-instructions.md,
.github/instructions/backlog-tasks.instructions.md, .github/agents/architecture.agent.md,
.github/agents/feature-architecture.agent.md, .github/agents/task-planner.agent.md,
.github/agents/tests-creation.agent.md, .claude/agents/implementation.md, .claude/agents/task-planner.md,
.claude/agents/tests-creation.md, .claude/skills/fastapi-api-patterns/SKILL.md,
.claude/skills/type-model-boundaries/SKILL.md, .claude/skills/implementation-planning/SKILL.md,
.claude/skills/architecture-review/SKILL.md, .claude/skills/groom-backlog/SKILL.md,
.claude/skills/plan-task/SKILL.md, .claude/skills/tdd-implementation/SKILL.md,
.claude/skills/tests-creation/SKILL.md, .claude/skills/python-quality-gates/SKILL.md,
.claude/skills/backlog-task-workflow/SKILL.md. None reference app/packages as a business-logic
statement, app/infrastructure/services/{providers,dependencies}.py, @lru_cache providers, or the
deleted records (layers.md, capability-packages.md, events.md — confirmed via `ls decisions/`;
no file in the repo references them today).

No decision record is out of date for this ticket; all citations below point at records that exist
on disk (verified against `ls decisions/`).

## Step 1 — CLAUDE.md

Replace "Architecture Boundaries" (current lines 39-46) with target six layers + explicit transitional
note, dropping the app/infrastructure/services/ claim entirely (it does not exist):

  ## Architecture Boundaries

  Target: six layers under `app/` — `server` (host) -> `features` -> `capabilities` ->
  `infrastructure` -> `integrations` -> `contracts`. Each layer imports only what
  `decisions/plugin-architecture.md`'s table allows; `contracts/` is the public plugin API
  and imports nothing else from the app. Read that record for the table — it is not
  reproduced here.

  Today's `main`: `app/features/`, `app/capabilities/` and `app/contracts/` don't exist yet.
  Business logic lives in `app/packages/<domain>`, and legacy `app/modules/` is being rebuilt
  surface by surface into the target layers (`decisions/plugin-architecture.md` and
  `decisions/migration.md` Migration/Tolerated-until sections govern what's still allowed —
  follow those records, not a stale copy here, as packages move). `app/modules` is frozen
  legacy: never cite it as an architectural reference. `app/packages/access` is a useful
  shape reference, not absolute truth.

  `decisions/` holds the authoritative ADRs and is the first source of truth. Web research
  fills gaps; it does not override a current ADR.

Replace "Import boundaries" (current lines 48-56):

  ### Import boundaries

  Target: features and capabilities never import `infrastructure` or `server` directly. The
  host (`server/`) registers one factory per `contracts` Protocol in a type-keyed registry
  (svcs); entry points (HTTP routes, Slack/Teams handlers, jobs) resolve what they need from
  a container scoped to that call. Services take dependencies through their constructor and
  never look them up mid-method (`decisions/dependency-injection.md`).

  Tolerated today, until that registry lands: features call `app/infrastructure/<service>/...`
  provider functions directly, some behind `@lru_cache`. Don't extend that pattern for a new
  service — treat a new module-level singleton provider as a bug in a file you're touching
  (ask first if it would blow the size gate), not something to add for consistency.

Leave "Type model boundaries" unchanged (no drift found).

Replace "Settings" (current lines 66-70):

  ### Settings

  Target: each owner defines its typed settings slice next to its code —
  `app/features/<feature>/settings.py`, `app/capabilities/<capability>/settings.py`,
  `app/infrastructure/<service>/settings.py`, `app/integrations/<vendor>/settings.py`
  (`decisions/configuration.md`). Do not grow root settings aggregators for an owner-specific
  concern; pass services the narrowest slice they need.

  Today: feature settings still live at `app/packages/<feature>/settings.py` until that
  package moves. See `settings-singleton` skill.

Replace "Plugins and startup" (current lines 72-78):

  ### Plugins and startup

  Discovery, registration and initialization are startup-driven via lifespan. Target: every
  feature and capability is a `pyproject.toml` entry-point loaded once by
  `pm.load_setuptools_entrypoints`, and each entry point carries a per-environment enablement
  key read from typed configuration — a disabled plugin registers nothing
  (`decisions/plugins.md`). Never register at import time; no side-effecting `__init__.py`
  bodies. Design new packages plugin-registerable from day one.

  Today: filesystem-walk discovery (`auto_discover_plugins`) is what actually runs; no entry
  points are declared yet and there is no enablement configuration (`decisions/plugins.md`
  Tolerated-until section, TASK-110). See `plugin-registration-lifespan` skill.

In "Task Workflow (Backlog.md)", amend the one-task-per-session line (current lines 132-134) to
record the user-approved stacked-PR relaxation for doc-2, without weakening the one-task-per-PR rule:

  - One task per session, one branch, one PR — except a stacked-PR chain the user has
    explicitly authorized in the session (for example the doc-2 delivery sequence), where a
    session works through several dependent tasks in order; each task still gets its own
    branch and its own PR. Check off acceptance criteria one by one as each is verified.
    Agents stop at `In Progress` with notes; **only humans move a task to Done.**

Leave "Customization Map" and the disjointness rule (line 9) unchanged: the codebase-researcher
sweep found no overlapping passage between CLAUDE.md and .github/copilot-instructions.md (AC4
already holds; no edit needed there).

## Step 2 — .github/instructions/packages-python.instructions.md

Rewrite the intro (lines 7-8) and the infrastructure-import bullet (lines 10-15) to state the
target registry and the tolerated-today direct provider import, dropping the
app/infrastructure/services/{providers,dependencies}.py claim:

  This is the **business logic** layer, moving to `app/features/<feature>/`
  (`decisions/plugin-architecture.md`, `decisions/feature-packages.md`). Shared platform
  capabilities belong in `app/infrastructure`, not here; `app/modules` is legacy and is never
  a pattern to copy.

  - **Never add a new concrete infrastructure import for a service this package doesn't
    already reach.** Target: resolve core services from the `contracts`-keyed registry the
    host builds in `server/` (`decisions/dependency-injection.md`). Until that registry
    lands, this layer still calls `app/infrastructure/<service>/...` provider functions
    directly — tolerated on code you're not otherwise touching, not a pattern to extend.

Rewrite the Settings bullet (line 31):

  - **Settings** — target: `app/features/<feature>/settings.py` (`decisions/configuration.md`).
    Until this package moves, its settings stay at `app/packages/<feature>/settings.py`. Do
    not add package-owned fields to root aggregators, and pass services the narrowest slice
    they need rather than a root settings object.

Leave the rest (type boundaries, registration, route handlers) unchanged — no drift found there.

## Step 3 — .github/instructions/infrastructure-python.instructions.md

Rewrite lines 7-8:

  This is the **shared platform** layer: capabilities more than one feature depends on.
  Business logic belongs in `app/features/<domain>` (today, `app/packages/<domain>`), never
  here (`decisions/plugin-architecture.md`).

Rewrite the object-assembly bullet (lines 12-15):

  - **Object assembly lives in provider/dependency layers**, not inside services. Target: the
    host registers one factory per `contracts` Protocol in a svcs registry
    (`decisions/dependency-injection.md`); entry points resolve from a per-call container.
    Until that registry lands, providers expose cached singletons (`@lru_cache(maxsize=1)`)
    — don't add a new one, that pattern is being retired.

## Step 4 — .github/instructions/tests-python.instructions.md

Rewrite the lru_cache bullet (lines 18-19):

  - **Clear `@lru_cache` provider caches between tests where a fixture still relies on one.**
    This pattern is being replaced by per-call svcs registrations
    (`decisions/dependency-injection.md`); a new test should register a Protocol-conformant
    fake against the registry instead of adding another cache to clear.

## Step 5 — .github/agents/codebase-researcher.agent.md

Rewrite point 4 (current lines 23-25):

  4. Note the layer of each hit against `decisions/plugin-architecture.md`'s six-layer
     target (`server`/`features`/`capabilities`/`infrastructure`/`integrations`/`contracts`).
     Today most business logic is still `app/packages` and legacy surfaces are in
     `app/modules` (**legacy** — flag it, never cite it as a pattern to follow).

## Step 6 — .github/agents/implementation.agent.md

Rewrite the business-logic bullet (current line 41):

  - Business logic target is `app/features/<feature>` (today still `app/packages/<domain>` —
    `decisions/plugin-architecture.md` Migration); no new business logic in
    `app/infrastructure`; `app/modules` is legacy and is not a pattern to copy.

Leave the "one task per session/branch/PR" line (line 46) as-is — it still states the default
correctly; the stacked-PR exception is a session-level authorization recorded in CLAUDE.md, not a
default this agent file needs to restate (cross-task note below).

## Step 7 — .claude/agents/architecture.md

Rewrite the layer-alignment bullet (current lines ~28-29):

  - Align with the six-layer target in `decisions/plugin-architecture.md`
    (`server`/`features`/`capabilities`/`infrastructure`/`integrations`/`contracts`); today
    business logic is still `app/packages`, moving to `app/features` per that record's
    Migration section — don't restate its table here. Require pluggy registration and
    lifespan startup; enforce settings partitioning and type boundary rules.

## Step 8 — .claude/agents/codebase-researcher.md

Same fix as Step 5, mirrored (current lines 22-24):

  4. Note which layer each hit lives in against `decisions/plugin-architecture.md`'s six-layer
     target (`server`/`features`/`capabilities`/`infrastructure`/`integrations`/`contracts`).
     Today most business logic is still `app/packages` and legacy surfaces are in
     `app/modules` (**legacy** — flag it, never cite it as a pattern to follow).

## Step 9 — .claude/agents/feature-architecture.md

Rewrite the business-logic bullet (current lines ~28-29):

  - Business logic target is `app/features` (today still `app/packages`); shared platform
    capabilities in `app/infrastructure`; `app/modules` is legacy and never a reference
    (`decisions/plugin-architecture.md`).

## Step 10 — .claude/skills/feature-architecture/SKILL.md

Same fix, mirrored (current lines ~51-52):

  - Business logic target is `app/features` (today still `app/packages`); shared platform
    capabilities in `app/infrastructure`; `app/modules` is never a reference
    (`decisions/plugin-architecture.md`).

## Step 11 — .claude/skills/settings-singleton/SKILL.md

Rewrite Core Rule 1 (current line 12):

  1. Target: settings live with their owner next to its code —
     `app/features/<feature>/settings.py` for features, `app/capabilities/<capability>/settings.py`
     for capabilities (`decisions/configuration.md`). Today, settings still live at
     `app/packages/<feature>/settings.py` until that package moves.

Rewrite the Provider Pattern's first bullet (current line 20):

  - Today: `@lru_cache(maxsize=1)` module-level providers are the tolerated pattern until the
    host's svcs registry lands (`decisions/dependency-injection.md`) — don't add a new one for
    a new service. Target: the host registers each service as a factory in a type-keyed
    registry; entry points resolve it from a per-call container.

Leave the CORS/environment-identity sections unchanged — they already correctly describe
`ENVIRONMENT`/`PREFIX` as today's reality with no false target claim, and are outside this
task's architecture-boundary scope.

## Step 12 — .claude/skills/testing-standards/SKILL.md

Rewrite the Fixtures section's lru_cache paragraph and example (current lines ~65-76):

  ## Fixtures

  Narrow-slice settings only. Today's `@lru_cache` module-level providers are tolerated until
  the svcs registry lands (`decisions/dependency-injection.md`) and still need clearing
  between tests:

  ```python
  @pytest.fixture(autouse=True)
  def _clear_caches():
      yield
      from app.packages.myfeature import providers  # app/features/<feature> once moved
      providers.get_service.cache_clear()
  ```

  Once a package's services resolve from the svcs registry, replace this with a fresh
  registry per test that registers Protocol-conformant fakes — there is no cache to clear.

## Step 13 — .claude/skills/plugin-registration-lifespan/SKILL.md (minor addition)

Add one line to the Core Checklist (after point 1) naming the still-missing enablement
mechanism, since the task's drift note calls this out explicitly:

  Target: each entry point also carries a per-environment enablement key read from typed
  configuration; the host skips a disabled plugin before registering it
  (`decisions/plugins.md`, `decisions/configuration.md`). This configuration layer doesn't
  exist on `main` yet — until it does, every declared entry point is effectively always-on.

## AC traceability

- AC1 (CLAUDE.md states six layers + import rules, cites plugin-architecture.md, drops
  infrastructure/services/ and the deleted records): Step 1.
- AC2 (grep over CLAUDE.md, .github/, .claude/ finds no reference to the deleted records or to
  infrastructure/services/{providers,dependencies}.py): Steps 1-4 remove the only three
  occurrences found (CLAUDE.md, packages-python.instructions.md); verify with the grep in
  Verification below.
- AC3 (every skill/agent file restating an architecture rule distinguishes target from
  tolerated-today and links the record instead of copying its table): Steps 1-13, all of which
  add a "target ... today ..." split and a decision-record citation in place of a bare
  `app/packages`/`app/infrastructure` claim.
- AC4 (CLAUDE.md and copilot-instructions.md stay disjoint): already holds; no edit needed,
  confirmed by the codebase-researcher sweep (no shared passage) and re-checked by grep.

## Verification (docs-only — no pytest/mypy/ruff; these are the task's real gates)

Run after the edits, from repo root:

  rg -n "app/infrastructure/services/(providers|dependencies)\.py" CLAUDE.md .github .claude
  rg -n "decisions/(layers|capability-packages|events)\.md" CLAUDE.md .github .claude decisions
  rg -n "app/packages" CLAUDE.md .github .claude   # every remaining hit must read as "today" text, not a target claim
  rg -n "lru_cache" .claude/skills .github/instructions   # every remaining hit must be framed as tolerated-today

All four must return either nothing (first two) or only lines explicitly framed as transitional
(last two) — read each hit to confirm, don't just count them.

Also re-run `cd app && uv run ruff check .` and `mypy`/`pytest` only if any edit accidentally
touched a `.py` file (it should not — every change here is to `.md` front matter/body).

## Assumptions and doubts

- Assumes decisions/plugin-architecture.md, dependency-injection.md, plugins.md, configuration.md,
  feature-packages.md and migration.md are the current accepted text on `main` at the moment this
  plan executes — re-diff them before editing if TASK-105/TASK-106/TASK-18/TASK-110 (currently
  "To Do" but shown modified in `git status`) changed any cited record in the meantime.
- Assumes no other in-flight change is concurrently editing these same 13 guidance files; `git
  status` shows only `backlog/tasks/*.md` modified, not these paths, so this should be safe to
  verify again with `git diff --stat -- CLAUDE.md .github .claude` immediately before editing.
- Assumes "tolerated today" language should name the blocking ticket (TASK-109, TASK-110, TASK-18)
  only where the cited decision record already names it, to avoid this doc drifting again the
  moment a ticket ships — verified against each record's own Migration section above.

## Blast radius and rollback

- Zero runtime risk: no `.py`, config, CI or infra file changes. A `git revert` of the single PR
  fully restores the previous guidance text.
- Ordering: none. This PR has no prerequisite and no dependent code change; it only affects what
  future agent sessions read.

## Cross-task findings (not edited here, reported only)

- `.github/agents/implementation.agent.md:46` and `.claude/agents/task-planner.md:35` also state
  "one task per session/branch/PR" without the stacked-PR exception now recorded in CLAUDE.md.
  Left alone here: they still state the correct default, and the exception is a session-level user
  authorization rather than a standing agent rule. Flag for a human call on whether to mirror the
  wording later.
- `.claude/skills/settings-singleton/SKILL.md`'s "Platform-presentation config" section still
  points transport settings at `app/infrastructure/<platform>/settings.py`; TASK-26.2 (in the
  dependency graph under TASK-106) moves Slack transport settings to `app/server/slack/`. Left
  untouched here — it's a transport-settings-location question, not this task's
  architecture-boundary scope, and editing it now would pre-empt TASK-26.2's own decision.
- TASK-105, TASK-106, TASK-110, TASK-18, TASK-25.4, TASK-25.10, TASK-26.1, TASK-26.2, TASK-35,
  TASK-36, TASK-37, TASK-37.1, TASK-38, TASK-39, TASK-52, TASK-53, TASK-88 all show as modified in
  `git status` at planning time (likely other sessions realigning the backlog in parallel). None of
  their files were read or touched by this plan; noted so the human reviewer knows this PR is
  independent of that churn.
- Task's own description/ACs: verified accurate against current `main` and current `decisions/`
  content — no CLI edit needed to TASK-104 itself.

## Size-gate note

13 files exceeds the ~10-file rule-of-thumb, but every edit is a small, mechanical paragraph swap
(no file changes are structural), the whole diff is documentation only, and it is explicitly
supposed to be one standalone PR per `backlog/docs/doc-2` Wave 0. Estimated total diff is well
under 150 changed lines. Not decomposed into subtasks per this task's own instructions; if a
reviewer would rather see it as CLAUDE.md+instructions first and agents/skills second, that is a
PR-splitting choice at review time, not a backlog decomposition.

## Addendum (coordinator-requested, 15 files total)

The other backlog tasks shown modified in `git status` are this session's own realignment work,
not parallel sessions — the "parallel session churn" cross-task finding above is retracted.

Two more files carry the stacked-PR-chain exception and must match CLAUDE.md's Task Workflow
wording, plus point agents at the session-mechanics skill and handoff docs:

## Step 14 — .github/agents/implementation.agent.md

Rewrite the backlog-tasks bullet (current line 45, "one task per session/branch/PR"):

  - Backlog tasks: CLI-only mutations, ACs checked off one by one as verified, never set a
    task to Done, one task per branch/PR — except a stacked-PR chain the user has explicitly
    authorized in the session (for example a doc-2 stack), where a session works through
    several dependent tasks in order; each still gets its own branch and PR. See the
    `stacked-pr-session` skill and `backlog/docs/stacks/` for handoff mechanics between
    sessions on a stack.

## Step 15 — .claude/agents/task-planner.md

Rewrite the "One task per session" bullet (current line 35):

  - One task per session — except a stacked-PR chain the user has explicitly authorized (for
    example a doc-2 stack), where a session plans or works through several dependent tasks in
    order, still one task per branch/PR. See the `stacked-pr-session` skill and
    `backlog/docs/stacks/` for handoff mechanics. Unrelated work found during research becomes
    a new task, not scope creep.

## AC traceability (addendum)

Steps 14-15 are not required by TASK-104's four ACs (which scope to architecture-boundary
restatements), but are in scope per the coordinator's explicit instruction to keep the
stacked-PR-chain exception consistent everywhere it's restated, alongside CLAUDE.md's Step 1
edit.

## File count (revised)

15 files total (13 above + Steps 14-15). Still one PR: the two additions are one-line-per-file
swaps: total diff remains well under 150 changed lines.
<!-- SECTION:PLAN:END -->
