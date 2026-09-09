---
name: Backlog Task Files Rules
description: Rules for files under backlog/ — task markdown is CLI-owned and must never be hand-edited.
applyTo: backlog/**
---

- **Never hand-edit files under `backlog/tasks/`** (or `completed/`, `archive/`,
  `drafts/`). The frontmatter and the `SECTION:DESCRIPTION`, `AC:BEGIN` and
  `DOD:BEGIN` markers are owned by the backlog CLI; hand edits corrupt them and the
  corruption is not obvious until a later CLI call fails.
- Mutate tasks only via `backlog task edit` / `backlog task create`; read them with
  `backlog task view <id> --plain`. See the `backlog-task-workflow` skill.
- **Never set a task's status to `Done`.** Agents stop at `In Progress` with notes;
  humans close tasks after verifying the Definition of Done.
- Check off acceptance criteria one at a time as each is verified
  (`--check-ac <index>`), never as a batch at the end.
- Every task headed for implementation needs a human-approved implementation plan
  (`backlog task edit <id> --plan`) and must fit a single reviewable PR — decompose
  oversized tasks per the `implementation-planning` skill.
- `auto_commit` is false: the CLI edits files but never commits. Git stays manual.
- Docs under `backlog/docs/` are editable via `backlog doc` commands. Note that
  this repo's **authoritative decision records live at the repo root under
  `decisions/`**, not `backlog/decisions/`; task `references:` point there.
