---
id: doc-19
title: Stack L2 handoff
type: guide
created_date: '2026-11-27T18:22:00Z'
updated_date: '2026-11-27T18:32:00Z'
---
## Stack

- Name: Stack L2, the remainder of Stack L (doc-16, finished at L6a on 2026-11-25): the declare cutover and its deletion layer, then timeline capture and the stale nudge, summarize, and the list sheet as a write-only projection. Trunk: `main`; `gh stack init` on main 3c196467 (#1897), 2026-11-27.
- doc-2 line: "Legacy rebuild by surface"; doc-11 rows 18.L9b, 18.L9b.1, 18.L10b-18.L10d, 18.L11, 18.L11b, then 18.L12 (config PRs from main, not stacked). Side rows from main: 18.L9c (TASK-145.7.11, after 18.L9b bakes), 18.L9d (TASK-199 offered severity levels as configuration, after 18.L9b merges).
- Program plan: TASK-145.7's plan (rules, PR table, domain gate) and the slice plans of 145.7.10, 145.9 and 145.12. Deletion-layer rule: decisions/migration.md step 5 (rides with 18.L9b).
- Branches: `stack-l2/<task-id>-<slug>`; side PRs `task-<id>-<slug>` from an up-to-date `main`.
- Planning: the agent plans each layer with the `implementation-planning` and `backlog-task-workflow` skills (directly or through the `task-planner` agent), writes it with `backlog task edit <id> --plan`, and stops for approval.
- Merges: squash, bottom-up, re-approval per layer after rebase; at least two stacked PRs open before any closes (stacked-pr-session skill); never merge the top layer while more layers are planned. Cutovers merge one at a time, each in a quiet window, each one git revert. 18.L9b.1 merges only after its exit criterion (7 days deployed, the post-deploy check recorded on TASK-145.7.10, no revert, one declare on the new path).
- Never stage: `backlog/docs/doc-11*`, `doc-15*`, `backlog/docs/stacks/doc-16*` (deleted locally once carried here), `backlog/archive/docs/doc-6*`, `doc-8*`, `doc-9*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, `coordinated-incidents-executive-briefing.md`, `task-168-*.md`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 18.L9b | TASK-145.7.10 declare cutover: /incident, the form, locale toggle, alert buttons, SEV0 (legacy left on disk for the revert; size exception) | `stack-l2/task-145.7.10-declare-cutover` | - | ready | 2026-11-27 implemented; gates green (mypy 33/11 unchanged, pytest 8369 passed); all ACs checked. Carries decisions/migration.md step 5, the TASK-145.7.13 Done change, the deletion of doc-5/7/10/13, this doc, and the stacked-pr-session rule. Task stays In Progress until the post-deploy check. |
| 18.L9b.1 | TASK-145.7.10.1 delete the legacy declare, models/incidents.py, the L5r guard, dev add-incident/load-incidents (deletion only) | `stack-l2/task-145.7.10.1-delete-legacy-declare` | - | plan approved | prepared this session above 18.L9b once the human runs `gh stack add`; PR open until the exit criterion |
| 18.L10b | TASK-145.9.2 cut over timeline capture and the stale nudge | `stack-l2/task-145.9.2-capture-nudge` | - | planned (outline) | waits 145.9.1, 145.8.1, 145.8.5, 145.7.10; at pickup check TASK-189's outcome and the TASK-145.9.2 note on the scheduled-meeting nudge |
| 18.L10c | TASK-145.9.3 summarize moved into response (pure move, size exception) | `stack-l2/task-145.9.3-summarize-move` | - | planned (outline) | waits 145.9.2, 25.10.3 |
| 18.L10d | TASK-145.9.4 core security guard, transcript rendering, summarize command check | `stack-l2/task-145.9.4-guard-rendering` | - | planned (outline) | waits 145.9.3 |
| 18.L11 | TASK-145.12.2 list write-only; sheet import and dev incident commands deleted | `stack-l2/task-145.12.2-list-write-only` | - | planned (outline) | waits 145.7.10, 145.9.2; then 18.L12 (human reruns the job) |
| 18.L11b | TASK-145.12.3 list rebuild job; fills column F; deletes the channel-id fallback | `stack-l2/task-145.12.3-list-rebuild` | - | planned (outline) | waits 145.12.2; confirm nobody edits the sheet by hand |

## Position

- /workspace on `stack-l2/task-145.7.10-declare-cutover` at 3c196467 (= origin/main, #1897), 18.L9b uncommitted and gated: app code and tests, decisions/migration.md step 5, the TASK-145.7.10, 145.7.13 and new TASK-199 task files, `.claude/skills/stacked-pr-session/SKILL.md` (the two-open-PRs rule), this doc, and the staged deletion of doc-5, doc-7, doc-10, doc-13. doc-17's citation edit is uncommitted and rides with the next Stack M commit.
- Baselines on main 3c196467: mypy 33 errors in 11 files; import contracts 15 kept; test seams 47 strict / 12 legacy (9 after 18.L9b).
- Carried from doc-16: 18.L8 apply 2026-11-26 (upgraded 331, roles_mapped 17, pending 0; throttled at 2 WCU, raised to 100 for the last two runs, restored); the upgrade job is off (#1895). 18.L12 reruns it once TASK-145.12.2 is deployed (dry_run, apply, off; reports on TASK-145.13), with write capacity raised first or the on-demand billing task.
- Tooling: `gh stack sync` aborts a rebase on conflict; use `gh stack rebase`, resolve, `gh stack rebase --continue`. Stash untracked files first (`git stash push --include-untracked -m ...`), pop after. Before any push or PR command, `gh pr list --head <branch> --state all`. Finished stacks may still be listed in `.git/gh-stack`; `gh stack view` on main asks which stack.
- Background agents: none.

## Next actions

1. **human**: commit and submit 18.L9b (commands in the session's final message). No terraform, IAM, SSM or task-definition env change, so deploy-checks are not required; the new `[incident_core] dev_conversation_names` key is a configuration-file key (base false, local true).
2. **human**: `gh stack add stack-l2/task-145.7.10.1-delete-legacy-declare`, then tell the agent.
3. **agent**: prepare 18.L9b.1 (TASK-145.7.10.1, deletion only, plan approved): S11-S15 of TASK-145.7.10's plan; gates; PR stays open until the exit criterion.
4. **human**: merge 18.L9b in a quiet window once reviewed (18.L9b.1 submitted above it); deploy-checks post summary; the post-deploy check in a test incident channel (TASK-145.7.10 plan section 8 step 4) and report it.
5. **agent**: record the post-deploy check on TASK-145.7.10, close it; start the 18.L9b.1 exit-criterion clock (deploy date).
6. **agent**: plan 18.L10b (TASK-145.9.2) against main, stacked above 18.L9b.1.

## Open decisions

1. Type-check tests? `[tool.mypy] exclude = ["^tests/"]` hides missed awaits and stale test stubs (69 pre-existing test-only errors in 6 files, found at L3b). Whether to open a task is the human's call; not part of this stack.

## Planning queue

- Approved: 18.L9b (TASK-145.7.10, 2026-11-26), 18.L9b.1 (TASK-145.7.10.1, with it).
- Outline only, plan in full at pickup: 18.L10b-18.L10d (TASK-145.9.2-145.9.4), 18.L11 (TASK-145.12.2), 18.L11b (TASK-145.12.3). Side: 18.L9c (TASK-145.7.11) after 18.L9b bakes; 18.L9d (TASK-199, created 2026-11-27 by the human's severity ruling) after 18.L9b merges.
