---
name: groom-backlog
description: Read-only sweep of To Do backlog tasks for readiness — missing plans, unmeasurable acceptance criteria, missing references, or scope too large for a single PR.
argument-hint: "[optional milestone or label filter]"
disable-model-invocation: true
---

# Groom the Backlog

Audit To Do tasks for planning readiness. Filter: `$ARGUMENTS` (optional).

**Run as**: `task-planner` agent · Tier L (Claude Haiku 4.5) — this is a
checklist sweep, not design work.

**Read-only.** Do not edit tasks, create tasks, or change statuses. Propose CLI
commands for the human instead.

## Steps

1. `backlog task list --plain -s "To Do"` (respect any filter given above).
2. For each task, `backlog task view <id> --plain` and assess:
   - Is there an implementation plan section? (No plan = not ready to implement.)
   - Are the ACs outcome-focused and independently verifiable, or vague?
   - Are `references:` present for tasks touching decision-record territory?
   - Does the described scope obviously exceed the single-PR size gate
     ([implementation-planning](../implementation-planning/SKILL.md))?
   - Are `--dep` dependencies consistent with the described ordering?
3. Report a readiness table: task id · verdict (ready to plan / needs grooming /
   needs decomposition) · the specific gaps.
4. Recommend which tasks to run `/plan-task` on next, **in dependency order**.

Keep it short: one line per healthy task, detail only where there are gaps.
