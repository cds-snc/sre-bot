---
id: doc-7
title: Stack I handoff
type: guide
created_date: '2026-10-09 13:34'
updated_date: '2026-10-09 13:53'
---
# Stack I handoff

## Stack

- Name: Stack I, human-first incident status updates. Trunk: `main`. gh stack: not yet initialised (the human runs `gh stack init` with layer 1).
- doc-2 line: none yet. The stack implements coordinator TASK-144, planned in backlog doc-6. doc-6 is the uncommitted planning record and is never staged with a layer.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-144.1 merge scribe platforms/ into entrypoints/ | `fix/incident_scribe_shape` | - | ready | Mechanical. ACs 1-5 checked, gate output in the notes (4476 passed; mypy 48 repo-wide, 0 in touched files; lint-imports 10 kept). Branch kept from the planning session (human, 2026-10-09) instead of `stack-i/task-144.1-scribe-entrypoints`; its PR carries 6f89a897 (TASK-144 planning) under the layer commit, folded by the squash merge. Not yet committed: the human commits it (Next actions 1). |
| 2 | TASK-144.2 human-first records and README | `stack-i/task-144.2-human-first-records` | - | planned | Docs only. Its feature-packages.md edit can land because layer 1 sits below it. |
| 3 | TASK-144.3 service and store: start, save, AI-fill | `stack-i/task-144.3-...` | - | planned | |
| 4 | TASK-144.4 modal: start by hand and save draft | `stack-i/task-144.4-...` | - | planned | |
| 5 | TASK-144.5 modal: AI inside the form | `stack-i/task-144.5-...` | - | planned | |

## Position

- Checked out: `fix/incident_scribe_shape` (main af6a316e plus 6f89a897, the TASK-144 planning commit, which creates every TASK-144.x task file). This branch is layer 1. Layer 1's changes are uncommitted: `app/`, the TASK-144.1 task file and this doc.
- Never stage `backlog/docs/doc-6*`.
- No background agents.

## Next actions

1. **human**: commit layer 1 on the current branch and adopt it as the stack's bottom layer:
   ```
   git add app/ backlog/tasks/ backlog/docs/stacks/
   git commit -m "Merge scribe platforms into entrypoints"
   gh stack init fix/incident_scribe_shape
   gh stack submit
   gh pr view --web
   ```
2. **human**: record plan approval on TASK-144.2 with a `--comment` ("Plan approved (human, <date>)"). The skill requires that comment before an agent implements a layer.
3. **agent**: `gh stack add stack-i/task-144.2-human-first-records`, then execute TASK-144.2 from its plan (docs only), ending with the commit/submit block for layer 2 and the resume prompt for layer 3.
4. **human**: review layer 1 as a move: compare the function inventory of the deleted `platforms/slack.py` with `entrypoints/slack.py` plus `entrypoints/slack_views.py` (the check is in the TASK-144.1 notes).

## Open decisions

- Approval of the plans for TASK-144.2 to TASK-144.5 (each has a plan; none has an approval comment yet).

## Planning queue

- Empty: TASK-144.2 to TASK-144.5 all have plans. They wait only on the human's approval comments (Open decisions).
