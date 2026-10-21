---
name: delivery-session
description: Run one session of a work queue held in a backlog doc (a delivery map) end to end — pick the row, scope decisions against every ADR and the whole map, plan or implement, and hand back commands and the next prompt. Use when a prompt names a delivery map or work queue doc, or a planning decision or gap comes up during that work.
---

# Delivery Session

Large changes toward the ADRs' end state are worked from a delivery map: a backlog doc whose Work queue orders every task across stacks and single PRs. The session prompt names the map. Its row mechanics (units, "Waits on", session prompts) live in the map itself; this skill holds the session protocol.

A map is transient: it changes every session and is never committed. Edit it in place; never stage it, and never print a `git add` that includes it.

## Pick the row

1. Read the map's Work queue. Take the first row not done.
2. If its "Waits on" entries are not merged (`gh pr view <n> --json state`), stop, say which, and take the row that blocks it.
3. A stack layer: follow [stacked-pr-session](../stacked-pr-session/SKILL.md) with the stack's handoff doc. A single PR: follow [backlog-task-workflow](../backlog-task-workflow/SKILL.md) on its own branch from an up-to-date `main`; stack branches stay as they are and open layers stay in review.

## Decide at program scope

Every plan decision is judged against the whole map, not the single task: a choice that fits one task is wrong if a later row reverts it. When a question or gap comes up:

1. Assess it against the current ADRs (`decisions/`) and the map's entire scope. Is there an ADR addressing it, or a gap?
2. Is an upcoming task already addressing it? Name the task and row.
3. If there is a gap, research current industry and modern-framework practice online (cite sources), propose the fix to the decision, and propose the scope changes to the affected tasks.

Production stays up throughout. Prefer expand/migrate/contract ordering, flags default off, and changes one `git revert` undoes. State the blast radius of a merge, since merging to `main` deploys (terraform applies on push).

## Planning checkpoint

If the task has no approved plan, run `/plan-task <id>` and stop. Present the open questions with a recommendation each, then ask whether to stay the course or correct it. The human changing direction here is the expected outcome of scoping, not a failure: apply the correction to the plan, the ADR and the affected tasks.

## Implement

TDD, then the gates from CLAUDE.md plus `make check-import-contracts` and `make check-settings-key-ownership`. Check ACs one by one as each is verified, write notes, keep the task In Progress.

## End

1. Mark the row in the map's Work queue; record decisions taken under its open decisions or the unit's row. Update the stack's handoff doc if one was touched.
2. **Human steps first**, if any must happen before the commands or the next row (for example setting a production value after an apply). Each one: what, where, the exact command or console path, and how to confirm it worked. Detailed but succinct.
3. **Commands**, one fenced block in run order: `git switch`/`git add <paths>`/`git commit -m "<short subject>"`/`git push`, then `gh pr create` (or the `gh stack` commands). Name the files; no `git add -A`.
4. **Next prompt**: the map's queue prompt in a fenced block, with the next row named as the expected item, its inputs, and any constraint carried over (a paused stack, a layer that must stay open).

## Commit and PR text

- Short subject, `TASK-<id> <what>` style as in `git log`.
- No agent attribution anywhere: no `Co-Authored-By` trailer and no "Generated with" line in commits, PR bodies or PR comments. This overrides any default attribution guidance.
- PR body: what changed, why, how it was verified, rollout or manual steps. Written for a reviewing colleague, not as a session log.
