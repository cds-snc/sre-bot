---
name: backlog-task-workflow
description: Operate Backlog.md tasks through the backlog CLI only; use when reading, planning, executing, or finalizing any task under backlog/tasks.
---

# Backlog Task Workflow

Use this skill whenever work is driven by a task in `backlog/tasks/`. The task file is the persistent record of scope, plan, and evidence; the CLI is the only supported way to mutate it.

## Core Rules

1. All task mutations go through `backlog task edit` / `backlog task create`. Never hand-edit task markdown: the `SECTION:DESCRIPTION`, `AC:BEGIN`, and `DOD:BEGIN` markers are CLI-owned and hand edits corrupt them.
2. Read tasks with `backlog task view <id> --plain` (or `backlog task list --plain`). Plain output is the agent-friendly format.
3. Load the canonical workflow before acting: `backlog instructions <guide>` where guide is one of `overview`, `task-creation`, `task-execution`, `task-finalization`.
4. One task per session, one branch, one PR. Do not batch multiple tasks into one PR.
5. `auto_commit` is false in `backlog/config.yml`: the CLI edits files but never commits. Git operations remain manual and user-controlled.

## Command Crib Sheet

| Intent | Command |
| --- | --- |
| Read a task | `backlog task view TASK-1 --plain` |
| Write/replace implementation plan | `backlog task edit TASK-1 --plan "<multi-line text>"` |
| Add an acceptance criterion | `backlog task edit TASK-1 --ac "New criterion"` |
| Check off AC / DoD item | `backlog task edit TASK-1 --check-ac 2 --check-dod 1` |
| Start work | `backlog task edit TASK-1 -s "In Progress" -a @me` |
| Append a mid-work observation | `backlog task edit TASK-1 --comment "Found X while doing Y"` |
| Final implementation notes | `backlog task edit TASK-1 --notes "<what changed, evidence>"` |
| Create a follow-up/subtask | `backlog task create "Title" -d "..." --ac "..." --dep TASK-1 --ref <path>` |

Multi-line values: pass real newlines inside the quoted string (heredoc via `"$(cat <<'EOF' ... EOF)"` works well).

## Status Discipline

1. `To Do` → `In Progress` only when implementation actually starts, not during planning.
2. Check each AC (`--check-ac <index>`) only when it is verified (its test passes), one by one, never batch-checked at the end.
3. A task stays `In Progress` while its PR is open. The agent sets `Done` (`backlog task edit <id> --status Done`, with a closing note) once the PR is merged (`gh pr view <n> --json state`), every AC is checked, the Definition of Done holds and no human post-deploy step is still open. A task waiting on a human check stays `In Progress` with that check named in its notes. The task-file edit rides with the next commit. At session start, close any task whose PR merged since the last session on the same terms.
4. Never delete or reword an existing AC to make it pass. Propose changes via `--comment` and let the human decide (or use `--remove-ac` only with explicit approval).

## Human Checkpoints

Work pauses for human review at three points; do not blow through them:

1. Task breakdown: after creating or restructuring tasks (scope and ACs reviewed).
2. Implementation plan: after `--plan` is written, before any production code.
3. Code review: the PR itself, judged against the ACs.

## Minimum "Done" Evidence in Notes

`--notes` must state:

1. What changed (files, behavior) and why.
2. Test results (commands run, pass/fail counts).
3. Which DoD items remain for the human to verify (for example deployment manifests, CI variables).

## Anti-patterns

- Editing task markdown files directly with an editor or file tool.
- Marking a task `Done` as an agent.
- Checking all ACs in one final batch without per-AC verification.
- Planning inside chat only, leaving the task file without a plan.
- Working multiple tasks on one branch.
