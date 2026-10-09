---
name: stacked-pr-session
description: Start, resume or end a session that works a doc-2 stacked-PR chain (gh stack). Use when a session begins on a stack, when the user says "resume stack X", and before ending any session that touched a stack, so the next session knows exactly where things stand.
---

# Stacked PR Session

Backlog doc-2 (Delivery Sequence and Stacked Pull Requests) says which stacks exist and how they are used. This skill covers the session mechanics: one handoff doc per stack, a fixed start routine, and a fixed end routine that finishes with a resume prompt.

## Rules

- One layer is one backlog task, one branch and one PR. A layer's commit holds only its own task's files.
- Implement a layer only when its plan is approved (a task comment records the approval).
- A session may carry several layers of one stack. Record the position in the handoff doc before switching layers.
- Git and `gh stack` write operations are run by the human. The agent prints the exact commands to run, in order, and runs read-only checks itself (`git status`, `git log`, `gh stack view`, `gh pr view`). The agent runs a write command only when the human asks for that specific command.
- Branch names are `<stack>/<task-id>-<slug>`, for example `stack-a/task-18-import-linter`. A planning layer is `<stack>/plan`.
- If a lower layer needs a fix, change that layer (`gh stack checkout <branch>`, commit, then `gh stack rebase`). Never patch it from a higher layer.

## Handoff doc

Each stack has one doc under `backlog/docs/stacks/`, created with `backlog doc create "<Stack> handoff" -p stacks -t guide` and replaced with `backlog doc update <doc-id> --content`. It holds the current state only; history lives in git and in task comments. Sections:

1. **Stack**: name, trunk, and the doc-2 line it implements.
2. **Layers**: a table with one row per layer, bottom first. Columns: #, task, branch, PR, state, notes. The state is one of `planned`, `plan approved`, `in progress`, `ready` (gates green, committed), `in review`, `merged`.
3. **Position**: the branch checked out, uncommitted work and what it belongs to, and any background agents still running.
4. **Next actions**: an ordered list, each marked **human** (with exact commands) or **agent**.
5. **Open decisions**: questions waiting on the human.
6. **Planning queue**: layers still without an approved plan, and what each one waits on.

## Start or resume

1. Read doc-2 and the stack's handoff doc.
2. Reconcile the doc with reality: `git status`, `git branch --show-current`, `gh stack view`, and `backlog task view <id> --plain` for the current layer. Check PR state for any layer marked `in review`.
3. Report the differences (a merged PR, a rebased branch, uncommitted work), then fix the handoff doc.
4. Continue with the first **agent** next action, or hand the human the first **human** action.

## End

1. Make sure every layer touched this session has task notes and checked ACs through the CLI, and stays at `In Progress`. Only humans set Done.
2. Check the PR state of every layer marked `in review` (`gh pr view <n> --json state`). For each merged layer whose task is not Done yet, print the command the human runs to close it: `backlog task edit <id> --status Done`. The task-file edit is committed with the next layer.
3. Print the commands that put the human on the next layer's branch before the next session starts, in order:
   - if a lower layer merged: `gh stack sync` (or `gh stack rebase`), then `gh stack submit` to update the PR bases;
   - `gh stack checkout <top branch>` if the top of the stack is not checked out;
   - `gh stack add <next-layer branch>`, which creates the next layer's branch on top of the stack and checks it out.
   Record these as **human** next actions in the handoff doc, and use the new branch as the expected position in the resume prompt.
4. Rewrite the handoff doc so that someone with no memory of this session could continue.
5. End the final message with a resume prompt in a fenced block:

```text
Resume <Stack> using the stacked-pr-session skill.
Handoff: backlog doc <doc-id> (backlog/docs/stacks/<file>).
Expected position: branch <branch>, layer <n> (<task-id>), state <state>.
First action: <the first next action, verbatim from the handoff doc>.
```
