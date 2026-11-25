---
id: doc-17
title: Stack M handoff
type: guide
created_date: '2026-11-20T21:03:00Z'
updated_date: '2026-11-25T20:34:00Z'
---
## Stack

- Name: Stack M, incident/postmortem: the postmortem meeting rebuilt on an incident-owned scheduling port with an industry availability model and a meeting lifecycle (TASK-145.10, coordinator over 145.10.1-145.10.6), then the report draft moved into postmortem and scribe deleted (TASK-145.11).
- doc-2 line: "Legacy rebuild by surface": Stack M (TASK-145.10 -> TASK-145.11; TASK-138 superseded by the TASK-169 ruling). doc-11 row 18b, unit "Stack M", Lane A.
- Program plan: TASK-145.10's plan (rules, layer table with waits/blast radius/revert, decisions, NC1-NC10, ADR edits per layer). Rulings: TASK-145.10 comment of 2026-11-20 (human approval). 145.10 D6 "English first line" is superseded by decisions/languages.md (TASK-193): shared text (channel posts, the calendar event) in LanguagePolicy.shared_languages in the instance order; views and private replies in reply_languages. Label rule (languages.md, 2026-11-25): a label a platform caps (Slack modal title, button) shows the first language, an uncapped label (calendar event title) carries every language joined by " / ".
- Trunk `main`. Branches: stacked layers `stack-m/<task-id>-<slug>`; side PRs `task-<id>-<slug>` from an up-to-date `main`.
- Planning: the agent plans each layer in full at pickup (implementation-planning and backlog-task-workflow skills), writes it with `backlog task edit <id> --plan`, and stops for approval.
- Merges: squash, bottom-up, re-approval per layer after rebase; at least two stacked PRs open before any closes (doc-13); never merge the top layer while more layers are planned. M3 and M4b change production; each merges alone in a quiet window, one git revert. M4b merges soon after M3 (hand edits on the shared calendar are risky).
- Task status: the agent sets a layer Done once its PR is merged, every AC is checked and no human post-deploy step is open (rule of 2026-11-20).
- Never stage: `backlog/docs/doc-11*`, `doc-15*`, `backlog/docs/stacks/doc-16*`, `backlog/archive/docs/doc-6*`, `doc-8*`, `doc-9*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md`, `large-scale-incident-analysis.md`, `access-vs-team-analysis.md`, `coordinated-incidents-executive-briefing.md`, `task-168-webhooks-*.md`, `.github/skills/` (untracked, not ours). Also left out of Stack M commits: `.claude/skills/delivery-session/SKILL.md` (modified) and `.claude/skills/delivery-session/change-notice.md` (untracked), present before the M2b session and not part of any layer.
- gh stack: `gh stack sync` aborts a rebase on conflict; use `gh stack rebase`, resolve, `gh stack rebase --continue`. Stash untracked files first (`git stash push --include-untracked -m ...`), pop after. Before any push or PR command, `gh pr list --head <branch> --state all`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| M1 | TASK-145.10.1 verbatim move dissolving features/incident/scheduling/ | `stack-m/task-145.10.1-dissolve-scheduling` | #1884 | merged | merged 2026-11-25 17:26Z as 8696f5c7; TASK-145.10.1 Done (task-file edit rides with M2b's commit) |
| M2a | TASK-145.10.2 core MeetingScheduler + CalendarAvailability ports, Google Calendar adapters, fakes; integrations/canada_holidays, HolidayCalendar port, adapter, fake | `stack-m/task-145.10.2-meeting-scheduler-port` | #1885 | in review | rebased onto main 87471ee9 by gh stack sync and resubmitted; re-approval required; ACs 1-11 checked, In Progress; may merge once M2b's PR is open above it AND the two pre-merge human checks are recorded on TASK-145.10.2 (below) |
| M2b | TASK-145.10.3 postmortem availability model, settings, schedule service, views, EN/FR catalogue, Sentinel sink; core members/account_emails and MeetingRequest label; task-id rule (migration.md rule 7) and its guard | `stack-m/task-145.10.3-availability-model` | #1888 | in review | commit f7a4716d submitted 2026-11-25; second commit (docstring cleanup, rule 7, check-task-references guard, CI step) uncommitted, gates green (pytest 8332, mypy 33/11 pre-existing); ACs 1-5 checked, In Progress; dark, rule-1 exception; D14 fallback: no plugin.py (M3 adds it) |
| M3 | TASK-145.10.4 cutover; plugin.py with entry point incident.postmortem; legacy deleted (AC #6); NC1-NC13 in the PR body | `stack-m/task-145.10.4-cutover` | - | planned (outline) | plan in full at pickup; hand-offs in its 2026-11-25 comments (plugin.py calls entrypoints/texts.register_catalogue; preview wiring via dispatch_action; pins :136/:159/:175/:187); TASK-145.10 AC #7 (show displays the meeting link) placed here at planning; human checks before merge (below) |
| M4a | TASK-145.10.5 core incident-role check (IC, ops lead, postmortem owner; fallback declared_by); incident-management.md rule | `stack-m/task-145.10.5-...` | - | planned (outline) | dark until M4b |
| M4b | TASK-145.10.6 meeting lifecycle: claim before booking, scheduled view (Reschedule, Cancel, Close; Recreate when missing), reschedule (events.patch), cancel, follow-up after the end, timeline kinds, audit | `stack-m/task-145.10.6-...` | - | planned (outline) | "missing" wording changed 2026-11-25 (recreated by the next schedule, M2b rule); confirm a clear-reference store operation at pickup; A1 result decides a "same time" option |
| M5 | TASK-145.11 report draft into postmortem, scribe deleted | - | - | planned (outline) | waits on 145.9 (Stack L rows 18.L10b-L10d), 134 merged; re-plan at pickup |

## Position

- Branch: `stack-m/task-145.10.3-availability-model` at f7a4716d (#1888, above #1885), with the second M2b commit uncommitted: the docstring cleanup, decisions/migration.md rule 7, CLAUDE.md and python-quality-gates skill lines, the task-reference guard with its test, baseline, make target and CI step, and the task-file and doc edits.
- 2026-11-25 slip, Lane B worktree: the first M2b command block ran in /home/vscode/worktrees/sre-bot-webhooks, committing only the TASK-37.1 task file as c5396461 on stack-w/task-37.1-content-loader (unpushed) and stashing doc-18 (stash "WIP on stack-w/task-37.1-content-loader: c5396461"). Fix (human, while no Lane B session edits there): git reset HEAD~1, then git stash pop of that stash.
- Background agents: none.

## Next actions

1. **human**: in /workspace, check the branch is stack-m/task-145.10.3-availability-model, stage the second M2b commit (app, decisions, CLAUDE.md, .claude/skills/python-quality-gates, .github/workflows/ci_code.yml, backlog/tasks, doc-17), commit "TASK-145.10.3 Task ids in code are removal markers only", `gh stack submit`; add the rule and the guard to #1888's body.
2. **human**: re-approve #1885 after its rebase; before it merges, record on TASK-145.10.2: the TASK-86 past-retro-event check, and one live create/get/patch/delete on the dev calendar (A1 get on a deleted event, including whether a cancelled event keeps its times, which M4b uses; A2 client-supplied id replay returns 409; A4 patch notification and attendee replacement). Then #1885 may merge (M2b is open above it); then `gh stack sync` (or `gh stack rebase` on conflict) and `gh stack submit`. The agent then closes TASK-145.10.2.
3. **agent**: once M2b is in review, plan M3 (TASK-145.10.4) in full with /plan-task 145.10.4 against M2b's tree, after the human runs `gh stack add stack-m/task-145.10.4-cutover` with M2b checked out; stop for approval.
- While Stack M layers wait on review, Lane A's next row is doc-11 row 18.L6c (TASK-145.8.9 side PR from main, unblocked by #1887).

## Open decisions

No decision open. Rulings: TASK-145.10 comment of 2026-11-20; M2a OQ1-OQ6 approved as revised 2026-11-25 (TASK-145.10.2); M2b plan approved as written 2026-11-25 (TASK-145.10.3 comment), with the human's rulings: every policy, tuning and bound value a typed [incident_postmortem] setting (holiday_lookup_failure proceed|refuse, default proceed); an existing meeting is shown and booking refused (modify = M4b); a meeting deleted outside the bot is recreated by the next schedule (key <incident_id>:postmortem:after:<deleted id>).
Pending human checks:
- Before M2a (#1885) merges: TASK-86 past-retro-event check; one live create/get/patch/delete on the dev calendar (A1, A2, A4).
- TASK-183 checklist: the delegated Workspace user owns "SRE - IFS Group Calendar"; people's sharing reduced to "See all event details".
- Before M3 merges: INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production (boot requires it); no Sentinel query reads the schedule-button event (incident_retro_scheduled now fires per booking, NC5 extended).

## Planning queue

- 145.10.4 (M3): outline; plan in full at pickup on M2b's tree. AC #6 deletes the legacy calendar/holiday code and requires the [canada_holidays] tenant at boot; TASK-145.10 AC #7 placed here; PR body lists NC1-NC13; creates plugin.py and the entry point.
- 145.10.5 (M4a), 145.10.6 (M4b): outlines; plan in full at pickup.
- 145.11 (M5): outline; re-plan at pickup after 145.9.4 merges.
