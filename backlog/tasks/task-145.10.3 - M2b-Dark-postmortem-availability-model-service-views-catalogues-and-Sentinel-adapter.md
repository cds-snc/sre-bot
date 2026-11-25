---
id: TASK-145.10.3
title: >-
  M2b Dark: postmortem availability model, service, views, catalogues and
  Sentinel adapter
status: To Do
assignee: []
created_date: '2026-11-20T22:04:00Z'
updated_date: '2026-11-25T15:18:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.10.2
parent_task_id: TASK-145.10
priority: medium
ordinal: 534000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M2b. Dark. Postmortem domain with the industry availability model replacing the legacy heuristic: free/busy/unknown per attendee (freebusy per-calendar errors are unknown, never free); required attendees default to the incident's role holders, optional are other channel members, two pickers (Must attend, Invite); a slot qualifies when no required attendee is busy (required unknown allowed but named) and an optional quorum (optional_quorum_percent) holds; earliest qualifying slot; an optional attendee busy for the whole window is excluded from blocking and named, a required one stops the search; explanations of who is busy or unknown and why no slot. NC7: per-date zoneinfo windows (DST) and holidays for every year the window crosses (kind (a); overlap with TASK-155 to check). Every tuning value is a typed [incident_postmortem] setting with a default. Service (service/schedule.py), views and EN/FR catalogues per the i18n rule of PR #1867 (view carries the opener's locale in private_metadata; nudge-opened modal bilingual; channel confirmation bilingual with English first line; French title Planifier la rétro 🗓️, within Slack's 24-character limit; the hint's zone name from the zone setting); Sentinel adapter postmortem/adapters/sentinel.py mirroring response (minimal named fields, observability.md:20). If over about 600 LOC, record the rule-1 exception. Branch stack-m/145.10.3-availability-model.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Availability model and explanations implemented as pure rules in postmortem/domain.py with injected clock and typed settings; unknown is never free
- [ ] #2 DST per-date windows and holidays across year boundaries are covered by deterministic tests (NC7)
- [ ] #3 service/schedule.py, slack_views.py and en-US and fr-FR catalogues exist and pass the parity check; Sentinel adapter sends minimal named fields
- [ ] #4 No consumer in production paths; size gate satisfied or the rule-1 exception recorded; ruff, mypy, the four make checks and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded outline (plan in full at pickup). Depends on M2a; i18n rule of PR #1867 must be merged or its rule read at pickup.
Grounding: moved pure rules in postmortem/domain.py (find_first_available_slot, identify_unavailable_users heuristic, get_utc_hour; legacy flags only a single busy block within one hour of both edges and treats calendar errors as free); legacy modal text in modules/incident/schedule_retro.py:97-232 (English only, title 'SRE - Schedule Retro'); response precedent for service/, providers.py, interfaces.py, adapters/sentinel.py, catalogues and register_i18n_resources; core Incident roles (incident_commander, operations_lead, postmortem_owner) and IncidentConversation.members (new, add here if not in M2a) for the pickers.
Steps: (1) domain: Availability (free/busy/unknown), SlotPolicy (frozen, built from settings), required/optional attendee model, qualifying-slot search (no required busy; required unknown named; optional quorum percent; earliest; whole-window-busy optional excluded and named, required stops the search), explanations; NC7 per-date zoneinfo windows, holidays for every year crossed (check overlap with TASK-155); (2) settings: meeting hours, timezone, duration, search days, earliest offset, optional_quorum_percent, unavailable rules, excluded attendee names, all typed with defaults in [incident_postmortem]; (3) service/schedule.py over MeetingScheduler, HolidayCalendar, IncidentStore.set_reference, IncidentConversation (post when writable); (4) slack_views.py and EN/FR catalogues (opener locale in private_metadata; nudge modal bilingual; confirmation bilingual English first; French title Planifier la rétro 🗓️ within 24 chars; zone name from setting); (5) adapters/sentinel.py + interfaces + providers (minimal named fields, observability.md:20). Tests under tests/unit/features/incident/postmortem/ (slot search, availability model, service with fakes, views, catalogue parity). Size: about 600 LOC; if over, record the rule-1 exception (dark, no consumer). Blast radius: dark; revert trivial.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T15:18:00Z

---

2026-11-25 (TASK-145.10.2 rulings): no [incident_postmortem] reminder_minutes (NC8 amended, reminder dropped). Consume HolidayCalendar.observed_federal_holidays(years) and decide fail-open vs fail-closed on a classified failure. The caller passes MeetingRequest.idempotency_key stable across re-claims of one booking attempt (see 145.10.6).

---
<!-- COMMENTS:END -->
