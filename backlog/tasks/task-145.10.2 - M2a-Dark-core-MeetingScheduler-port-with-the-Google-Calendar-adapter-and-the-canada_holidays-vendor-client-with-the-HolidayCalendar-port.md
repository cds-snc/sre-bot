---
id: TASK-145.10.2
title: >-
  M2a Dark: core MeetingScheduler port with the Google Calendar adapter, and the
  canada_holidays vendor client with the HolidayCalendar port
status: To Do
assignee: []
created_date: '2026-11-20T22:04:00Z'
updated_date: '2026-11-20T22:05:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.10.1
parent_task_id: TASK-145.10
priority: medium
ordinal: 533000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M2a. Dark, no consumer. (1) core MeetingScheduler port in core/api.py with purpose-neutral names (create, get, patch, delete): scheduling is domain-agnostic and may serve other incident meetings; a non-incident consumer is the TASK-169 trigger for a capability. Google Calendar adapter over integrations/google_workspace with explicit parameters: description, 10-minute popup reminder, one requestId source (TASK-86 folded in: NC8, kind (a); the legacy event_config was dropped by insert_event); guestsCanModify and guestsCanInviteOthers false (NC10, kind (b)). (2) New integrations/canada_holidays/ vendor client (httpx async; [canada_holidays] base_url, timeout_seconds, connect_retries; classify_canada_holidays_error; decisions/outbound-clients.md); HolidayCalendar port in postmortem/interfaces.py, adapter in postmortem/adapters/. ADR edits: configuration.md vendor-enablement line for a credential-less public vendor plus a Changes line; service-accounts.md rule 5 meetings line. Branch stack-m/145.10.2-scheduler-port-holidays-client.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 MeetingScheduler (create, get, patch, delete) is in core/api.py with a Google Calendar adapter returning classified OperationResults, one attempt on writes, to_thread for blocking calls
- [ ] #2 Events carry description, a 10-minute popup reminder and one requestId source; guests cannot modify or invite (NC8, NC10), pinned by adapter tests
- [ ] #3 integrations/canada_holidays/ client with [canada_holidays] settings (base_url, timeout_seconds, connect_retries) and classify_canada_holidays_error; HolidayCalendar port in postmortem/interfaces.py with its adapter in postmortem/adapters/; the verbatim get_federal_holidays from M1 is deleted
- [ ] #4 configuration.md (credential-less public vendor line and Changes line) and service-accounts.md rule 5 meetings line are amended
- [ ] #5 No consumer in production paths; ruff, mypy, make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded outline (plan in full at pickup; re-ground against main then). Depends on M1.
Grounding: core/adapters/google_meet.py is the pattern (async, asyncio.to_thread, classify_google_error, GoogleCredentialsRefused, OperationResult, VideoCall port at core/api.py:479); calendar adapter moved by M1 holds get_freebusy/insert_event with num_retries=0 and drops insert_event's **kwargs (legacy save_retro_event passed description, reminders and requestId that were discarded: TASK-86, NC8 kind (a)); the inserted body sets guestsCanModify and guestsCanInviteOthers true (NC10 kind (b) sets false). integrations/ vendor package shape: decisions/outbound-clients.md (client factory, classifier, settings slice, retries at construction, httpx); Slack/Google gateways are the models.
Steps: (1) MeetingScheduler Protocol in core/api.py (create, get, patch, delete; purpose-neutral MeetingRequest/ScheduledMeeting types in core/domain.py; no postmortem wording); (2) rewrite the Google Calendar adapter over explicit parameters, one requestId source; (3) integrations/canada_holidays/ (client.py httpx async, settings.py [canada_holidays] base_url, timeout_seconds, connect_retries, classify_canada_holidays_error, README); (4) HolidayCalendar Protocol in postmortem/interfaces.py and adapter in postmortem/adapters/ replacing M1's verbatim public_holidays.py (delete it and the requests_mock test); (5) config/base.toml keys, key-ownership; (6) ADR edits: configuration.md vendor-enablement line (credential-less public vendor: no tenant entry, slice holds only endpoint and transport tuning, always available, failures classified) plus Changes line; service-accounts.md rule 5 meetings line (calendar the bot user owns; people read/free-busy only; invitees cannot modify; changes go through the bot and are recorded on the incident). Tests: adapter body and classification tests, client tests with httpx mock, port fakes in core/adapters/in_memory.py. Size estimate about 380 new LOC, about 12 files: record rule-1 exception if over. Blast radius: dark; revert trivial. Open checks: production calendar owner per the service-accounts line (TASK-169/181); no scope list written here.
<!-- SECTION:PLAN:END -->
