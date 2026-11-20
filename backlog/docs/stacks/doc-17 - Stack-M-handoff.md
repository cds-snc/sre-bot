---
id: doc-17
title: Stack M handoff
type: guide
created_date: '2026-11-20T21:03:00Z'
updated_date: '2026-11-20T23:30:00Z'
---
## Stack

- Name: Stack M, incident/postmortem: the postmortem meeting rebuilt on an incident-owned scheduling port with an industry availability model and a meeting lifecycle (TASK-145.10, coordinator over 145.10.1-145.10.6), then the report draft moved into postmortem and scribe deleted (TASK-145.11).
- doc-2 line: "Legacy rebuild by surface": Stack M (TASK-145.10 -> TASK-145.11; TASK-138 superseded by the TASK-169 ruling). doc-11 row 18b, unit "Stack M".
- Program plan: TASK-145.10's plan (rules, layer table with waits/blast radius/revert, decisions, NC1-NC10, ADR edits per layer). Rulings: TASK-145.10 comment of 2026-11-20 (human approval).
- Trunk `main`. Branches: stacked layers `stack-m/<task-id>-<slug>`; side PRs `task-<id>-<slug>` from an up-to-date `main`.
- Planning: the agent plans each layer (implementation-planning and backlog-task-workflow skills, or the task-planner agent), writes it with `backlog task edit <id> --plan`, and stops for approval when the plan changes an approved assumption. M2a-M4b have grounded outlines; plan in full at pickup.
- Merges: squash, bottom-up, re-approval per layer after rebase; at least two stacked PRs open before any closes (doc-13); never merge the top layer while more layers are planned. M3 and M4b change production; each merges alone in a quiet window, one git revert. M4b merges soon after M3 (hand edits on the shared calendar are risky).
- Task status: the agent sets a layer Done once its PR is merged, every AC is checked and no human post-deploy step is open (rule of 2026-11-20).
- Never stage: `backlog/docs/doc-11*`, `doc-15*`, `backlog/archive/docs/doc-6*`, `doc-8*`, `doc-9*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, `coordinated-incidents-executive-briefing.md`, `.github/skills/` (untracked, not ours).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| M1 | TASK-145.10.1 verbatim move dissolving features/incident/scheduling/ (Calendar adapter -> core/adapters, availability -> postmortem/domain.py, holidays -> postmortem/adapters/public_holidays.py); contract (i), package_shape and seam baselines; incident-management.md :75/:137/:179 | `stack-m/task-145.10.1-dissolve-scheduling` | - (to submit) | ready | implemented 2026-11-20 in the working tree on main ac8f8186, gates green, ACs 1-5 checked, In Progress; no behaviour change; carries the planning changes (145.10 tasks, TASK-191/192, scope notes, instruction rule change, 17 closed task files, this doc); stays in review until M2a is open above it |
| M2a | TASK-145.10.2 core MeetingScheduler port (create/get/patch/delete), Calendar adapter (NC8 TASK-86, NC10 guests cannot modify), integrations/canada_holidays, HolidayCalendar; configuration.md + service-accounts.md lines | `stack-m/task-145.10.2-meeting-scheduler-port` | - | planned (outline) | dark |
| M2b | TASK-145.10.3 postmortem domain (industry availability model, required/optional attendees, NC7), service, views, EN/FR, Sentinel adapter | `stack-m/task-145.10.3-...` | - | planned (outline) | dark; size exception if > ~600 LOC |
| M3 | TASK-145.10.4 cutover; legacy deleted; NC1-NC10 in the PR body; pins :159/:175 edited | `stack-m/task-145.10.4-...` | - | planned (outline) | waits on #1867 merged; human checks before merge (below) |
| M4a | TASK-145.10.5 core incident-role check (IC, ops lead, postmortem owner; fallback declared_by); incident-management.md rule | `stack-m/task-145.10.5-...` | - | planned (outline) | dark until M4b |
| M4b | TASK-145.10.6 meeting lifecycle: claim before booking, scheduled view, reschedule (events.patch), cancel, follow-up after the end, timeline kinds, audit | `stack-m/task-145.10.6-...` | - | planned (outline) | confirm a clear-reference store operation at pickup |
| M5 | TASK-145.11 report draft into postmortem, scribe deleted | - | - | planned (outline) | waits on 145.9 (Stack L rows 18.L10b-L10d), 134 merged; re-plan at pickup |

## Position

- Branch: `main` (ac8f8186 = origin/main) with M1 implemented and uncommitted in the working tree; `stack-m/task-145.10.1-dissolve-scheduling` not yet created.
- Uncommitted work: all of it rides with M1's commit (M1 code, tests, baselines, ADR and README lines; TASK-145.10 and 145.10.1-.6, TASK-145.11 deps, TASK-191, TASK-192, scope-note comments, 17 closed task files, instruction rule change, this doc). Never-stage files above stay out.
- Background agents: none.

## Next actions

1. **human**: `gh stack init stack-m/task-145.10.1-dissolve-scheduling` from `main` (uncommitted work carries), then the `git add`/`git commit` from the session's command block, `gh pr list --head stack-m/task-145.10.1-dissolve-scheduling --state all` (expect none), `gh stack submit`, and set the PR body.
2. **human**: `gh stack add stack-m/task-145.10.2-meeting-scheduler-port` (M2a's branch above M1, checked out).
3. **agent**: plan M2a (TASK-145.10.2) in full with /plan-task against M1's tree; stop for approval.
4. **agent**: once approved, implement M2a TDD; after M2a's PR is open, M1 may merge (re-approval after any rebase).
- While M1 waits on review and M2a's plan waits on approval, the side row is doc-11 row 21 (TASK-168 design session).

## Open decisions

None open. Rulings of 2026-11-20 are on TASK-145.10 (comment). Pending human checks:
- Before M2a merges: a past retro event in Google Calendar has no description (TASK-86 precondition; if it has one, NC8 shrinks to the requestId cleanup).
- TASK-183 checklist: the delegated Workspace user owns "SRE - IFS Group Calendar"; people's sharing reduced to "See all event details".
- Before M3 merges: INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production (boot requires it); no Sentinel query reads the schedule-button event; #1867 merged.

## Planning queue

- 145.10.2-145.10.6: outlines; plan in full at pickup.
- 145.11: outline; re-plan at pickup after 145.9.4 merges.
