---
name: plan-task
description: Research a backlog task and write its implementation plan into the task via the backlog CLI, decomposing it first if too large for a single reviewable PR.
agent: task-planner
model: Claude Sonnet 5 (copilot)
---

Plan the backlog task given as input (task id, for example `TASK-1`). If no id was provided, ask for one.

Required steps:

1. `backlog task view <id> --plain` and `backlog instructions task-execution`.
2. Read all `references:` (decision records, linked issues).
3. Research the codebase; enumerate exact call sites (`path:line`) — no planning from memory.
4. Estimate diff size and apply the single-PR size gate (`implementation-planning` skill). If it trips, propose an expand/migrate/contract breakdown, get approval, create subtasks via `backlog task create ... --dep --parent`, then plan only the first slice.
5. Write the plan with `backlog task edit <id> --plan "..."`.
6. Add missing ACs via `--ac`; propose AC removals via `--comment`.
7. Stop for human review of the plan before any handoff.

Rules:

- CLI-only task edits; never hand-edit task markdown.
- No production code, no tests, no git commands in this workflow.
- Plan must include: ordered steps with exact files, AC-to-step-to-test traceability, test matrix, assumptions/doubts with verification, blast radius and rollback.
