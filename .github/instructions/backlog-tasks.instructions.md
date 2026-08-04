---
name: Backlog Task Files Rules
description: Use for files under backlog/; task markdown is CLI-owned and must not be hand-edited.
applyTo: backlog/**
---

- Never hand-edit files under `backlog/tasks/` (or `backlog/completed/`, `backlog/archive/`, `backlog/drafts/`): the frontmatter and `SECTION`/`AC`/`DOD` markers are owned by the backlog CLI and hand edits corrupt them.
- Mutate tasks only via `backlog task edit` / `backlog task create`; read via `backlog task view <id> --plain`. See the `backlog-task-workflow` skill.
- Never set a task's status to Done; humans close tasks after verifying the Definition of Done.
- Every task headed for implementation needs a human-approved implementation plan (`backlog task edit <id> --plan`), and its change must fit a single reviewable PR — decompose oversized tasks per the `implementation-planning` skill.
- Docs under `backlog/docs/` may be edited via `backlog doc` CLI commands. Note: this repo's authoritative decision records live at the repo root under `decisions/` (not `backlog/decisions/`); task `references:` point there.
