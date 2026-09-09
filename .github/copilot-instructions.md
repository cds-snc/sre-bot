# Copilot Operating Policy

> The project's engineering contract lives in **[`CLAUDE.md`](../CLAUDE.md)**, which
> VS Code loads automatically for every chat request on **every model** (GPT,
> Claude, MAI, Gemini) via `chat.useClaudeMdFile`. Read it first — it is not
> repeated here.
>
> This file adds only what is Copilot-specific: **model cost tiering**, agent
> routing, and the `.github/` customization surface.

## Model Cost Policy (Mandatory)

Copilot bills per token as AI credits (1 credit = $0.01 USD), so model choice —
not request count — is what drains the budget. Every agent, prompt and handoff in
this repo pins a model from **Tier L or Tier M**. Tier H is off-limits without
explicit human approval in the request.

Prices are USD per 1M tokens (input / output), verified 2026-09-09 against
[Models and pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing).
Re-verify before changing any pinned model.

### Tier L — low consumption (default for mechanical work)

| Model | In / Out | Best for |
| --- | --- | --- |
| GPT-5.6 Luna | 0.20 / 1.20 | file surveys, greps, summarizing, status sweeps |
| MAI-Code-1.1-Flash | 0.20 / 1.20 | mechanical edits, renames, formatting |
| GPT-5.4 nano | 0.20 / 1.25 | trivial lookups |
| GPT-5 mini | 0.25 / 2.00 | short scoped edits |
| Gemini 3.8 Flash | 0.75 / 3.75 | long-context reading (promo pricing to 2026-12-31) |
| GPT-5.4 mini | 0.75 / 4.50 | test scaffolding |
| Claude Haiku 4.5 | 1.00 / 5.00 | spec-driven test authoring, gate triage |

### Tier M — medium consumption (reasoning, design, implementation)

| Model | In / Out | Best for |
| --- | --- | --- |
| Claude Sonnet 5 | 2.00 / 10.00 | **default** for architecture, planning, implementation |
| GPT-5.3-Codex | 1.75 / 14.00 | code-heavy implementation fallback |
| GPT-5.6 Terra | 2.00 / 12.00 | general fallback |
| GPT-5.4 | 2.50 / 15.00 | general fallback |
| Claude Sonnet 4.6 | 3.00 / 15.00 | last-resort fallback |

### Tier H — do not select (2.5x–10x Tier M output cost)

Claude Opus 4.7 / 4.8 / 5 (5.00 / 25.00), Opus 4.8 fast mode and Claude Fable 5.x
(10.00 / 50.00), GPT-5.5 (5.00 / 30.00), GPT-5.6 Sol (4.00 / 20.00), GPT-6 Astra
(10.00 / 50.00).

If a task genuinely needs Tier H, say so and ask — do not switch silently.

### Routing rule

Pick the **cheapest tier that can do the job correctly**, and state the model in
the handoff. Escalate L → M only when the task requires multi-step reasoning,
cross-file design, or trade-off analysis. Never escalate for volume of text.

## Cost Discipline

These waste credits faster than model choice fixes:

- **Don't re-read what you already read.** File contents stay in context.
- **Delegate output-heavy exploration** to the `codebase-researcher` agent (Tier L)
  so raw file dumps never enter the expensive session.
- **Start a new session between unrelated tasks.** A polluted context re-bills every
  turn for tokens that no longer help.
- **Two failed corrections = restart** with a better prompt, not a third correction.
- **Scope investigations** to named files/globs. Never "investigate the codebase".
- Reach for `rg` over reading whole files; read the lines you need.
- Prefer `#tool:web/fetch` on a known doc URL over open-ended web search.

## Agent Routing

| Agent | Tier | Pinned model (fallback) | Use for |
| --- | --- | --- | --- |
| `codebase-researcher` | L | GPT-5.6 Luna (Claude Haiku 4.5) | read-only surveys, call-site enumeration |
| `tests-creation` | L | Claude Haiku 4.5 (GPT-5.4 mini) | failing tests from an approved spec |
| `task-planner` | M | Claude Sonnet 5 (GPT-5.4) | backlog task research + implementation plan |
| `implementation` | M | Claude Sonnet 5 (GPT-5.3-Codex) | production code against failing tests |
| `feature-architecture` | M | Claude Sonnet 5 (GPT-5.3-Codex) | one feature's contracts + test matrix |
| `architecture` | M | Claude Sonnet 5 (GPT-5.4) | app-level direction + decision records |

Workflow order: `architecture` → `feature-architecture` → `task-planner` →
`tests-creation` → `implementation`. Each stage hands off explicitly; do not skip
`task-planner` for anything that touches more than one file.

## Copilot Customization Surface

| File | Purpose |
| --- | --- |
| `CLAUDE.md` | always-on engineering contract (all models) |
| `.github/copilot-instructions.md` | this file — Copilot policy delta |
| `.claude/skills/<name>/SKILL.md` | skills, shared with Claude Code (`chat.useClaudeSkills`) |
| `.github/agents/*.agent.md` | Copilot custom agents (model-pinned) — **pick these** |
| `.github/instructions/*.instructions.md` | path-scoped rules via `applyTo` globs |
| `.vscode/mcp.json` | workspace MCP servers |

Skills live under `.claude/skills/` on purpose: VS Code and Claude Code both read
that directory, so one file serves every model. Do not create `.github/skills/`.

**Agents are the exception — they cannot be shared.** VS Code reads *both*
`.github/agents/*.agent.md` and `.claude/agents/*.md`, and the two formats express
`model:` and `tools:` differently, so each harness needs its own file. The
`.claude/agents/*.md` twins therefore carry `user-invocable: false`, which keeps
them out of the VS Code agents dropdown — otherwise every agent appears twice. In
Copilot always pick the `.github/agents/` one: only it carries the Tier L/M model
pin and the handoff buttons. Keep the two sets in sync when you change a role.

There is no `.github/prompts/` directory: prompt files are **deprecated for Agent
Host sessions** and are not loaded there. Every former prompt is now a workflow
skill (`disable-model-invocation: true`, so its description costs nothing until you
invoke it) and the model pinning moved to the agent files, which Copilot honors in
every session type. Add new workflows as skills, and run them under the agent named
at the top of the skill.

Available workflow commands: `/architecture-review`, `/feature-architecture`,
`/plan-task`, `/tests-creation`, `/tdd-implementation`, `/groom-backlog`,
`/python-quality-gates` — identical in Claude Code and Copilot.
