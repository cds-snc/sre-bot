---
id: TASK-145.10
title: >-
  Build incident/postmortem: schedule the postmortem meeting through the
  incident scheduling port
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-25T19:10:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.6
  - TASK-36.1.5
  - TASK-111.10
references:
  - https://github.com/cds-snc/sre-bot/issues/1688
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 360000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer D1 of TASK-145 and Stack M coordinator: plugin incident.postmortem, independent of the response slices after TASK-145.6. Rebuilds schedule_retro (the modal flow, the schedule button from the nudge, availability search and meeting creation) and adds the meeting lifecycle. A postmortem meeting is a meeting about the incident. Calendar operations are incident-owned: TASK-138 (calendar capability) is superseded by the TASK-169 ruling of 2026-11-05 (human), and a calendar capability waits for a non-incident consumer.

Split into six layers by the single-PR size gate (see the program plan): TASK-145.10.1 (M1, verbatim move dissolving features/incident/scheduling), 145.10.2 (M2a, MeetingScheduler port, Google Calendar adapter, canada_holidays client), 145.10.3 (M2b, availability model, service, views, catalogues), 145.10.4 (M3, cutover and legacy deletion), 145.10.5 (M4a, role check), 145.10.6 (M4b, meeting lifecycle). This task writes no code; it is Done when every layer is merged and the ADR edits have landed.

User-facing labels keep today's "retro" wording in the catalogues; the code and the record say postmortem. TASK-147 shares postmortem/ and nothing here is gated by its flag; TASK-145.11 moves the report draft in afterwards.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-145.10.1 (M1) is merged: scheduling/ dissolved, no behaviour change
- [ ] #2 TASK-145.10.2 (M2a) is merged: MeetingScheduler port, Google Calendar adapter and canada_holidays client in place, dark
- [ ] #3 TASK-145.10.3 (M2b) is merged: availability model, service, views, catalogues and Sentinel adapter in place, dark
- [ ] #4 TASK-145.10.4 (M3) is merged: incident.postmortem registered with calendar_id required, legacy retro scheduling deleted, named changes NC1-NC10 listed in its PR body, pins pass
- [ ] #5 TASK-145.10.5 (M4a) and TASK-145.10.6 (M4b) are merged: role check and meeting lifecycle in place
- [ ] #6 Every ADR edit named in the program plan has landed with its layer (incident-management.md, configuration.md, service-accounts.md, workplace-systems.md wording, features/incident/README.md)
- [ ] #7 incident show displays the postmortem meeting link from the record (a read-only line of the response show view built by TASK-145.8.3), replacing the Retro Link dropped there (TASK-145.8.3 OQ11, human 2026-11-17); delivered by the layer that writes the meeting reference (M3, TASK-145.10.4), placed there at its planning
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Program plan, approved 2026-11-20 (human) after re-plan against main ac8f8186. TASK-145.10 is the Stack M coordinator: it owns no code; its six subtasks do. Supersedes the single-PR plan (it tripped the size gate: about 520 new LOC, about 285 moved, about 430 deleted, about 30 files, a mechanical move mixed with behaviour).

## Rules
- One layer, one PR, branch stack-m/<task-id>-<slug>; each layer shippable and revertible by one git revert; main stays green after each merge. Order M1 -> M2a -> M2b -> M3 -> M4a -> M4b; TASK-145.11 depends on M4b (the last).
- No calendar capability (TASK-138 superseded by TASK-169, 2026-11-05 human): calendar code is incident-owned; a non-incident consumer is the trigger for a capability. The MeetingScheduler port uses purpose-neutral names.
- Every behaviour change is a named change of a migration.md step-4 kind (a)-(d), pinned before the cutover and listed in M3's PR body. Dead code in touched files is deleted. Policy and tuning values are typed settings with defaults (configuration.md). No Google scope list is written to any task or note.
- ADR and README edits ride with the layer that makes them true. TASK-147 shares postmortem/: nothing here is gated by its flag. TASK-145.11 moves the report draft in afterwards (postmortem/service/report.py, prompt.py), taking none of this scope.

## Layers
| Layer | Task | Kind | Waits on | Blast radius / revert |
| M1 | 145.10.1 verbatim move dissolving features/incident/scheduling | mechanical, no behaviour change | 145.6, 36.1.5 | none at runtime; revert restores both trees |
| M2a | 145.10.2 core MeetingScheduler port + Google Calendar adapter; integrations/canada_holidays client + HolidayCalendar port | dark | M1 | dark; revert trivial |
| M2b | 145.10.3 availability model, service, views, EN/FR catalogues, Sentinel adapter | dark (rule-1 exception if over about 600 LOC) | M2a | dark; revert trivial |
| M3 | 145.10.4 cutover, legacy deleted, value-scoped alias claimed | production-changing | M2b, PR #1867 merged | retro modal, nudge button and /sre incident schedule move; one git revert restores legacy |
| M4a | 145.10.5 core role check for meeting changes | dark | M3 | none; revert trivial |
| M4b | 145.10.6 meeting lifecycle (one upcoming meeting, reschedule, cancel, follow-up) | production-changing | M4a (merge soon after M3) | writes to a shared calendar; revert restores M3 behaviour, events already created stay |

## Design decisions
D1 Scheduling dissolves into core and postmortem because contract (i) makes postmortem and scheduling independent siblings and incident-management.md :98 and :179 retire adapter-only siblings. Calendar adapter in core/adapters beside google_meet.py; pure rules in postmortem/domain.py (feature-packages.md: domain.py = pure rules); the holiday client is a vendor integration (integrations/canada_holidays, outbound-clients.md) behind a HolidayCalendar port in postmortem/interfaces.py. postmortem/ has no calendar adapter; its adapters/ holds the holidays and Sentinel adapters.
D2 Plugin: entry point incident.postmortem = features.incident.postmortem.plugin (host reads settings.py before plugins load), contract (m) updated, requirement incident_postmortem.calendar_id (boot fails naming the key when empty, plugins.md), enablement keys (ci off).
D3 Ids: modal-internal ids under incident.postmortem.*; the nudge button via register_attachment_action('incident.postmortem.schedule', ..., legacy_callback_values={'archive_channel': ('schedule_retro',)}); TASK-145.13 removes the alias. The archive_channel_action schedule_retro branch is deleted in M3.
D4 Availability model (replaces the legacy single-busy-block heuristic): free/busy/unknown per attendee, freebusy errors are unknown never free; required attendees default to the incident's role holders, optional are other channel members ('Must attend' and 'Invite' pickers); a slot qualifies when no required attendee is busy (required unknown allowed but named) and the optional quorum (optional_quorum_percent) holds; earliest qualifying slot; explanations name who is busy or unknown and why no slot.
D5 One upcoming meeting per incident; the calendar owns the time and the record holds only the reference; state (none, upcoming, ended, missing) is derived, never stored. First booking open to any channel member; later changes limited to the commander, operations lead or postmortem owner (declared_by fallback).
D6 i18n per the rule of PR #1867: view carries the opener's locale in private_metadata; nudge-opened modal and channel confirmation bilingual (English first line); French title 'Planifier la rétro 🗓️' within Slack's 24-character limit; zone name in hints from the zone setting.

## Named changes (listed with kind in M3's PR body)
NC1 (a) refused calendar insert shows a failure view (pin first renamed test_legacy_only_*); NC2 (b) not-an-incident decided by the record, private localized reply; NC3 (b) meeting reference stored on the record; NC4 (b) EN/FR text; NC5 (b) minimal Sentinel payload (observability.md:20); NC6 (a) member without email skipped; NC7 (a) per-date DST windows and holidays for every year crossed (overlap with TASK-155 to check); NC8 (a) description, 10-minute reminder and one requestId source sent (TASK-86 folded in; event_config is sent, not deleted); NC9 (b) availability model, pins test_incident_retro_schedule_surface.py:159 and :175 edited citing the ruling; NC10 (b) guestsCanModify and guestsCanInviteOthers false.

## ADR edits per layer
M1 incident-management.md :75 (stale TASK-138 calendar sentence), :137, :179; M2a configuration.md vendor-enablement line for a credential-less public vendor plus a Changes line, service-accounts.md rule 5 meetings line; M3 incident-management.md Postmortem availability paragraph; M4a incident-management.md role rule (authorization.md object-level checks stay in the feature; feature-packages.md rule 4); M4b incident-management.md Postmortem paragraph and :44 line.

## Open checks (human or pickup)
INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production before M3 merges; no Sentinel query reads the schedule-button event (M3); PR #1867 merged before M3; TASK-181 may change the Calendar factory (whichever merges second adapts); TASK-189 or TASK-145.9.2 may replace the stale notice's buttons (alias still serves posted notices); host_configuration.py :247 line removable only if key ownership still validates the table; TASK-155 overlap on holidays; verify a bot can create events on the calendar the bot user owns (service-accounts rule 5).

## Verification (every layer)
ruff and targeted tests during TDD; at the end, from app/: make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, then once each, sequentially, full mypy and full pytest (tests --ignore=tests/smoke).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 re-ground: postmortem/ is shared with TASK-147 (postmortem as records: action items, narrative document, built dark behind a flag); this slice keeps scheduling only and adds nothing gated by that flag.

2026-11-05: TASK-138 superseded (TASK-169 ruling, 2026-11-05 (human), D5): every calendar consumer is incident; a calendar capability waits for a second suite or a non-incident consumer. Dependency on 138 removed.

2026-11-06 (TASK-36.1.2 OQ1/OQ3, human-approved): depends on TASK-36.1.5 (the retro pins) instead of the whole TASK-36.1. Rebuilt modal-internal ids take the incident.postmortem prefix as planned; the nudge's schedule button (archive_channel's schedule_retro branch, on messages already posted) keeps a registered legacy alias until TASK-145.13 (decisions/transport-slack.md). confirm_click is owned here, not by TASK-145.8.

2026-11-06 (TASK-36.1.5 pins): the retro pins capture legacy behaviour to rule on here: a refused calendar insert escapes handle_schedule_retro_submit, so the modal stays on 'Scheduling the retro...' and nothing is posted (its 'did not return a link' failure view is unreachable: insert_event raises, never returns None); schedule_event collects each attendee email twice (harmless); the unavailable-user rule flags only a single busy block within an hour of both range edges. Rewire test_incident_retro_schedule_surface.py to the rebuilt postmortem scheduling.

2026-11-16 (human, TASK-145.8.5.2 OQ7): claiming the schedule_retro value makes the schedule_retro branch of archive_channel_action unreachable; this task deletes that branch. TASK-145.13 deletes the listener and its registration.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-16T19:34:00Z

---

2026-11-16 (human, TASK-145.8.5 OQ3): the nudge's schedule button registers through a value-scoped alias (archive_channel scoped to schedule_retro, TASK-145.8.5.2), not a plain alias of the whole callback; until then that value falls through to the legacy listener. TASK-145.13 removes the alias.

---

created: 2026-11-20T22:06:00Z

---

2026-11-20 (human): program-scope rulings APPROVED as recommended: three-way-plus slicing into 145.10.1-145.10.6 (M1 move; M2a core port, Calendar adapter, canada_holidays; M2b industry availability model, service, views, EN/FR; M3 cutover NC1-NC10; M4a core incident-role check; M4b meeting lifecycle); OQ1 scheduling dissolved (TASK-138 archived; scheduling is domain-agnostic); OQ2 accepted, audit content -> TASK-191; OQ3 TASK-86 folded in (NC8); OQ4 i18n per #1867; OQ5 NC7 in M2b; OQ6 one upcoming meeting, reschedule/cancel/follow-up, calendar owns the time; OQ7 industry availability model with required/optional attendees; OQ8 integrations/canada_holidays; NC10 guests cannot modify; postmortem owner may also change the meeting; first booking stays open to any channel member; post-meeting state derived from the event; TASK-192 overdue reminders. Assessment and sources: doc-17 Open decisions.

---

created: 2026-11-25T15:18:00Z

---

2026-11-25 (human, TASK-145.10.2 rulings): NC8 amended to 'description and one requestId source sent'; the 10-minute reminder is dropped (Calendar applies events.reminders to the authenticated bot user only; attendees keep their own defaults) and no reminder_minutes setting is added. Calendar create and delete keep SDK retries (keyed create, 410 delete); only patch is one attempt. [canada_holidays] base_url is a tenant entry (self-hostable API). The booking idempotency key is stable across re-claims, never a claim token. Legacy deletions are on TASK-145.10.4 AC #6.

---

created: 2026-11-25T19:10:00Z

---

2026-11-25 (human, TASK-193 approved): D6's 'English first line' is superseded by the instance order (decisions/languages.md, [languages] shared); M3/M4 channel posts go through LanguagePolicy and MultilingualText; views and private replies in the user's language of choice. Note in doc-17 at the next Stack M session.

---
<!-- COMMENTS:END -->
