---
name: plan-task
description: Research a backlog task and write its implementation plan into the task via the backlog CLI, decomposing it first if too large for a single reviewable PR.
argument-hint: "[task-id]"
disable-model-invocation: true
---

# Plan a Backlog Task

Plan backlog task `$ARGUMENTS`. If no id was given, ask for one before doing anything else.

**Run as**: `task-planner` agent · Tier M (Claude Sonnet 5).
**Follow**: [backlog-task-workflow](../backlog-task-workflow/SKILL.md) and
[implementation-planning](../implementation-planning/SKILL.md).

This produces human checkpoint #2 — the reviewable implementation plan. It writes
no production code and no tests.

## Steps

1. `backlog task view <id> --plain`, then `backlog instructions task-execution`.
2. Read every file in the task's `references:` frontmatter (ADRs under `decisions/`)
   and any linked GitHub issues.
3. Research the codebase — run the searches the task implies (`rg`), read the
   affected files, and enumerate exact call sites as `path:line`. Include
   `terraform/`, `.github/workflows/` and `bin/` when config or environment
   behavior is involved. Delegate wide surveys to the `codebase-researcher` agent.
4. Estimate the diff (production files, production LOC, subsystems crossed) and
   apply the single-PR size gate.
5. **If the gate trips**: design an expand/migrate/contract slice sequence, present
   the breakdown (titles, scope, dependency order, per-slice size) for human
   approval, then create subtasks with
   `backlog task create ... --dep <id> --parent <id>` and plan only the first slice.
6. Write the plan: `backlog task edit <id> --plan "..."`.
7. Tighten acceptance criteria via `--ac`; propose removals via `--comment`, never
   by deleting.
8. **Stop and request human review.** No handoff until the plan is approved.

## Plan Must Contain

- Ordered steps naming exact files and what changes in each.
- AC → step → test traceability, in both directions.
- Test matrix: happy path, boundary, failure, and where relevant
  authorization/idempotency, with intended file names.
- Assumptions and doubts, each with how to verify it.
- Blast radius and rollback: what breaks if this ships wrong, whether one
  `git revert` restores service, and any ordering constraints.

## Hard Constraints

- Never hand-edit task markdown; all mutations via the backlog CLI.
- Never write production code or tests here. Never set a status to Done, and do
  not set In Progress during planning.
- Never run git commands.
- A plan exceeding the size gate must not be handed off — decompose first.
- One task per session. Unrelated work found during research becomes a new task
  via `backlog task create`, not scope creep.

## Output

Task restated (id, title, ACs) · references consulted · enumerated call sites ·
size estimate and gate verdict · decomposition performed (if any) with the CLI
commands run · the plan as written · AC changes · open questions for the reviewer.
