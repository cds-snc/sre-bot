---
id: doc-19
title: Stack L2 handoff
type: guide
created_date: '2026-11-27T18:22:00Z'
updated_date: '2026-11-27T19:14:00Z'
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
| 18.L9b | TASK-145.7.10 declare cutover: /incident, the form, locale toggle, alert buttons, SEV0 (legacy left on disk for the revert; size exception) | `stack-l2/task-145.7.10-declare-cutover` | #1900 | in review | committed 80b58cf4 2026-11-27; gates green (mypy 33/11, pytest 8369 passed); all ACs checked; task In Progress until the post-deploy check. |
| 18.L9b.1 | TASK-145.7.10.1 delete the legacy declare, models/incidents.py, the L5r guard, dev add-incident/load-incidents (deletion only) | `stack-l2/task-145.7.10.1-delete-legacy-declare` | - | ready | 2026-11-27 prepared (deletion only); gates green (mypy 32/10, pytest 8116 passed); ACs #1-#4 and #6 checked; #5 exit criterion open; PR stays open until it, then merges after 18.L9b. |
| 18.L10b | TASK-145.9.2 cut over timeline capture and the stale nudge | `stack-l2/task-145.9.2-capture-nudge` | - | planned (outline) | waits 145.9.1, 145.8.1, 145.8.5, 145.7.10; at pickup check TASK-189's outcome and the TASK-145.9.2 note on the scheduled-meeting nudge |
| 18.L10c | TASK-145.9.3 summarize moved into response (pure move, size exception) | `stack-l2/task-145.9.3-summarize-move` | - | planned (outline) | waits 145.9.2, 25.10.3 |
| 18.L10d | TASK-145.9.4 core security guard, transcript rendering, summarize command check | `stack-l2/task-145.9.4-guard-rendering` | - | planned (outline) | waits 145.9.3 |
| 18.L11 | TASK-145.12.2 list write-only; sheet import and dev incident commands deleted | `stack-l2/task-145.12.2-list-write-only` | - | planned (outline) | waits 145.7.10, 145.9.2; then 18.L12 (human reruns the job) |
| 18.L11b | TASK-145.12.3 list rebuild job; fills column F; deletes the channel-id fallback | `stack-l2/task-145.12.3-list-rebuild` | - | planned (outline) | waits 145.12.2; confirm nobody edits the sheet by hand |

## Position

- /workspace on `stack-l2/task-145.7.10.1-delete-legacy-declare` (created by `gh stack add` on 80b58cf4, the 18.L9b commit, #1900 open). 18.L9b.1 uncommitted: the deletion (app/modules, app/models, app/features/incident/core/adapters/legacy_rollback.py, tests), README and INVENTORY wording, locales, pyproject ignore, seam baseline (7 legacy), the TASK-145.7.10.1 and TASK-145.12.2 task files, this doc. doc-17's citation edit is uncommitted and rides with the next Stack M commit.
- Baselines: main 3c196467 mypy 33/11; after 18.L9b.1 32/10 (the deleted incident.py error). Import contracts 15 kept. Test seams 47 strict / 7 legacy after 18.L9b.1.
- Order coupling seen only in a targeted run: tests/modules/webhooks/ before test_webhook_route_payload_surface.py fails 4 payload pins; untouched by this stack, passes in the full suite's order (Lane B's area).
- Carried from doc-16: 18.L8 apply 2026-11-26 (upgraded 331, roles_mapped 17, pending 0; throttled at 2 WCU, raised to 100 for the last two runs, restored); the upgrade job is off (#1895). 18.L12 reruns it once TASK-145.12.2 is deployed (dry_run, apply, off; reports on TASK-145.13), with write capacity raised first or the on-demand billing task. With 18.L9b.1 merged no legacy writer is left.
- Tooling: `gh stack sync` aborts a rebase on conflict; use `gh stack rebase`, resolve, `gh stack rebase --continue`. Stash untracked files first, pop after. Before any push or PR command, `gh pr list --head <branch> --state all`.
- Background agents: none.

## Next actions

1. **human**: commit and submit 18.L9b.1 (commands in the session's final message); its PR stays open until the exit criterion.
2. **human**: review and merge 18.L9b (#1900) in a quiet window once reviewed; the post-deploy check in a test incident channel (TASK-145.7.10 plan section 8 step 4) and report it with the deploy date.
3. **agent**: record the post-deploy check on TASK-145.7.10 and close it; record the deploy date on TASK-145.7.10.1 (exit criterion clock).
4. **agent**: plan 18.L10b (TASK-145.9.2) against main, stacked above 18.L9b.1 (`gh stack add stack-l2/task-145.9.2-capture-nudge`, human); at pickup check TASK-189's outcome and the TASK-145.9.2 note on the scheduled-meeting nudge.
5. **human** (after 7 days, the check, no revert, one declare): merge 18.L9b.1 once a higher layer is submitted above it.

## Open decisions

1. Type-check tests? `[tool.mypy] exclude = ["^tests/"]` hides missed awaits and stale test stubs (69 pre-existing test-only errors in 6 files, found at L3b). Whether to open a task is the human's call; not part of this stack.

## Planning queue

- Approved: 18.L9b (TASK-145.7.10, 2026-11-26), 18.L9b.1 (TASK-145.7.10.1, with it).
- Outline only, plan in full at pickup: 18.L10b-18.L10d (TASK-145.9.2-145.9.4), 18.L11 (TASK-145.12.2), 18.L11b (TASK-145.12.3). Side: 18.L9c (TASK-145.7.11) after 18.L9b bakes; 18.L9d (TASK-199, created 2026-11-27 by the human's severity ruling) after 18.L9b merges.
