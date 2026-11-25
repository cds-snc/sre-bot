---
id: doc-17
title: Stack M handoff
type: guide
created_date: '2026-11-20T21:03:00Z'
updated_date: '2026-11-25T15:41:00Z'
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
| M1 | TASK-145.10.1 verbatim move dissolving features/incident/scheduling/ (Calendar adapter -> core/adapters, availability -> postmortem/domain.py, holidays -> postmortem/adapters/public_holidays.py); contract (i), package_shape and seam baselines; incident-management.md :75/:137/:179 | `stack-m/task-145.10.1-dissolve-scheduling` | #1884 | in review | committed a5acbdad on main ac8f8186 and submitted 2026-11-20, gates green, ACs 1-5 checked, In Progress; no behaviour change; carries the planning changes (145.10 tasks, TASK-191/192, scope notes, instruction rule change, 17 closed task files, this doc); stays in review until M2a is open above it |
| M2a | TASK-145.10.2 core MeetingScheduler + CalendarAvailability ports, Google Calendar adapters (key-derived event id = requestId, NC8 as amended: description, no reminder; NC10), fakes; integrations/canada_holidays ([canada_holidays.tenant] base_url in local/production), HolidayCalendar port, adapter, fake; configuration.md, service-accounts.md, outbound-clients.md lines | `stack-m/task-145.10.2-meeting-scheduler-port` | - (to submit) | ready | implemented 2026-11-25, gates green (pytest 8161, mypy 40/13 pre-existing, contracts 15 kept), ACs 1-11 checked, In Progress; dark, ~1050 prod lines / 16 files, rule-1 exception; legacy path untouched until M3; human checks before merge below |
| M2b | TASK-145.10.3 postmortem domain (industry availability model, required/optional attendees, NC7), service, views, EN/FR, Sentinel adapter | `stack-m/task-145.10.3-availability-model` | - | planned (outline) | dark; consumes CalendarAvailability, HolidayCalendar (years), MeetingScheduler; no reminder_minutes; decides fail-open/closed on a holiday failure; size exception if > ~600 LOC |
| M3 | TASK-145.10.4 cutover; legacy deleted; NC1-NC10 in the PR body; pins :159/:175 edited | `stack-m/task-145.10.4-...` | - | planned (outline) | waits on #1867 merged; human checks before merge (below) |
| M4a | TASK-145.10.5 core incident-role check (IC, ops lead, postmortem owner; fallback declared_by); incident-management.md rule | `stack-m/task-145.10.5-...` | - | planned (outline) | dark until M4b |
| M4b | TASK-145.10.6 meeting lifecycle: claim before booking, scheduled view, reschedule (events.patch), cancel, follow-up after the end, timeline kinds, audit | `stack-m/task-145.10.6-...` | - | planned (outline) | confirm a clear-reference store operation at pickup |
| M5 | TASK-145.11 report draft into postmortem, scribe deleted | - | - | planned (outline) | waits on 145.9 (Stack L rows 18.L10b-L10d), 134 merged; re-plan at pickup |

## Position

- Branch: `stack-m/task-145.10.2-meeting-scheduler-port` (above M1 a5acbdad), M2a implemented and uncommitted in the working tree.
- Uncommitted work: all of it is M2a's (code, tests, config, ADR lines, the TASK-145.10.2 plan/notes/ACs, the 2026-11-25 comments on 145.10, 145.10.3, 145.10.4 (new AC #6), 145.10.6, 86, 87.1, 87.3, and this doc). Never-stage files stay out.
- Background agents: none.

## Next actions

1. **human**: commit M2a (command block of the 2026-11-25 session), `gh pr list --head stack-m/task-145.10.2-meeting-scheduler-port --state all` (expect none), `gh stack submit`, set the PR body.
2. **human**: before M2a merges: the TASK-86 past-retro-event check and one live create/get/patch/delete on the dev calendar (A1, A2, A4); record the results on TASK-145.10.2.
3. **human**: once M2a's PR is open, M1 (#1884) may merge (re-approval after any rebase); then `gh stack sync` and `gh stack submit`.
4. **human**: `gh stack add stack-m/task-145.10.3-availability-model` (M2b's branch above M2a, checked out).
5. **agent**: plan M2b (TASK-145.10.3) in full with /plan-task against M2a's tree; stop for approval. Close TASK-145.10.1 once #1884 has merged.
- While a layer waits on review and M2b's plan waits on approval, the side row is doc-11 row 21 (TASK-168 design session).

## Open decisions

M2a rulings OQ1-OQ6 approved as revised 2026-11-25 (TASK-145.10.2 comments and plan section 0). No decision open.
Rulings of 2026-11-20 are on TASK-145.10 (comment). Pending human checks:
- Before M2a merges: a past retro event in Google Calendar has no description (TASK-86 precondition; if it has one, NC8 shrinks to the requestId cleanup).
- Before M2a merges: one live create/get/patch/delete on the dev calendar (A1 get on a deleted event, A2 client-supplied id replay returns 409, A4 patch notification and attendee replacement).
- TASK-183 checklist: the delegated Workspace user owns "SRE - IFS Group Calendar"; people's sharing reduced to "See all event details".
- Before M3 merges: INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production (boot requires it); no Sentinel query reads the schedule-button event; #1867 merged.

## Planning queue

- 145.10.3-145.10.6: outlines; plan in full at pickup. M2b decides fail-open/closed on a holiday-lookup failure and passes a booking key stable across re-claims; no reminder_minutes (NC8 amended). M3 (145.10.4) AC #6 deletes the legacy calendar/holiday code and requires the [canada_holidays] tenant at boot.
- 145.11: outline; re-plan at pickup after 145.9.4 merges.
