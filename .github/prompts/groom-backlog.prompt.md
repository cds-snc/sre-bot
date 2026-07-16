---
name: groom-backlog
description: Sweep To Do tasks for readiness — missing plans, unmeasurable acceptance criteria, missing references, or scope too large for a single PR.
agent: task-planner
model: Auto (copilot)
---

Audit the backlog for planning readiness. Read-only except for CLI comments explicitly approved by the human.

Steps:

1. `backlog task list --plain -s "To Do"` to enumerate candidates (respect any milestone/label filter given as input).
2. For each task, `backlog task view <id> --plain` and assess:
   - Has an implementation plan section? (Missing plan = not ready for implementation.)
   - Are ACs outcome-focused and independently verifiable, or vague/unmeasurable?
   - Are `references:` present for tasks touching decision-record territory?
   - Does the described scope obviously exceed the single-PR size gate (`implementation-planning` skill)? Flag tasks needing decomposition.
   - Are dependencies (`--dep`) consistent with the described ordering?
3. Report a readiness table: task id, verdict (ready to plan / needs grooming / needs decomposition), and the specific gaps.
4. Recommend which tasks to run `/plan-task` on next, in dependency order.

Rules:

- Do not edit tasks, create tasks, or change statuses in this sweep; propose CLI commands for the human (or a follow-up planning session) instead.
- Keep the report short: one line per healthy task, detail only where gaps exist.
