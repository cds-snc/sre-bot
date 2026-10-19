---
id: TASK-36.1.1
title: >-
  Pin the legacy /incident declare modal, locale toggle and alert buttons
  through the Bolt dispatch boundary, and extend the harness to legacy
  interactions
status: Done
assignee: []
created_date: '2026-10-15 20:49'
updated_date: '2026-10-19 16:35'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - decisions/transport-slack.md
parent_task_id: TASK-36.1
priority: high
ordinal: 395000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-36.1. Extends the TASK-36 harness so it registers through the real _register_legacy_handlers() step and drives actions, view submissions and events through App.dispatch, then pins the rows TASK-145.7 replaces: /incident, view incident_view, action incident_change_locale and action handle_incident_action_buttons. Also adds a registration-set test that names all 6 commands and 33 interactions registered by _register_legacy_handlers(), so later slices cannot drift.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The harness registers through the real _register_legacy_handlers() on a real Bolt App and exposes dispatch helpers for slash commands, block_actions or interactive_message actions, view_submission and events, with every Web API call, response_url post and external edge faked
- [x] #2 A registration-set test asserts the exact 6 commands, 18 actions, 11 views and 4 events (reaction_added and reaction_removed each twice: matcher and ack-only fallback) that _register_legacy_handlers() registers
- [x] #3 /incident, incident_view, incident_change_locale and handle_incident_action_buttons (call-incident and ignore-incident) each have a dispatch-driven test covering ack, Slack-visible calls and the success and error paths
- [x] #4 INVENTORY.md marks these rows pinned by this task and names TASK-145.7 as their rebuild ticket
- [x] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main 12805b0a (2026-10-15). Test-only: 0 production LOC, 0 production files. Touches 4 files under app/tests/integration/legacy_surface/ (conftest.py edited, two test files created, INVENTORY.md edited). Within the single-PR gate.

## Decomposition (TASK-36.1 split)
Counts checked against main: _register_legacy_handlers (server/lifespan.py:103) calls role, atip, aws, secret, webhook_helper, incident, incident_helper .register. Registrations: 6 commands (aws, talent-role, secret, atip, aiprp, incident); 18 actions; 11 views (the old description said 12: stale); 4 events; 33 interactions, 39 rows. This matches INVENTORY.md. 39 rows with a new harness extension exceeds one reviewable PR, so TASK-36.1 became a coordinator over TASK-36.1.1 (this task, gates TASK-145.7), .2 (16 incident_helper interactions), .3 (aws, role, secret, atip: 13 rows), .4 (webhook admin: 6 rows). TASK-145.7 now depends on TASK-36.1.1 only.

## Discovered state
- tests/integration/legacy_surface/conftest.py: build_harness (line 90) registers the six register_slack_commands hookimpls plus _register_legacy_slack_commands, never _register_legacy_handlers. RecordingApp records only commands. Commands reach handlers through a provider-owned client, but Bolt injects its own WebClient into action, view and event listeners, so the FakeSlackClient is not seen by them.
- test_slack_command_registration_surface.py asserts registered_commands == ["/dev-rant", "/dev-sre"] (line ~125) and a once-only Counter (line 72): the legacy handlers must NOT be added to build_harness.
- tests/factories/slack_bolt.py already has FakeSlackClient (calls_to), InlineExecutor, authorize_single_workspace, unpatched_app_init.
- Handlers under pin: modules/incident/incident.py (register 36; open_create_incident_modal 49: ack, users_info locale, views_open loading view, list_incident_folders, views_update; handle_change_locale_button 76: toggles en-US/fr-FR, views_update; submit 135: validation, create_incident_conversation, views_open success modal, log_to_sentinel, core.initiate_resources_creation, say on failure) and modules/incident/incident_alert.py (handle_incident_action_buttons 49: call-incident reuses the open-modal handler with private_metadata from the alert; ignore-incident acks, increments the webhook acknowledged count, rewrites the attachments and calls chat.update through api_call).
- Observed latent bug, not fixed here: submit() calls ack() at line 137 and then ack(response_action="errors") at the validation branch, so Slack never receives the errors. TASK-145.7 replaces submit() and the legacy module is deleted, so the pin records the observable behaviour (empty-body ack, no channel created) and the test docstring says the inline errors are not delivered. No production file is touched by this task.

## Steps
1. conftest.py: extract the Bolt-app construction in build_harness (unpatched App init, RecordingApp, authorize_single_workspace, InlineExecutor) into build_bolt_app(monkeypatch) used by both builders; no behaviour change to existing tests. Extend RecordingApp to also record action, view and event registrations as (kind, id, has_matcher) tuples. Fix the stale docstring "Wire the five hookimpls" (there are six).
2. conftest.py: add LegacyHandlerHarness plus a legacy_handler_harness fixture: build_bolt_app, then the real _register_legacy_handlers(app, structlog logger) (no hookimpls, no provider registration). Route Bolt's WebClient.api_call into a FakeSlackClient (api_method "views.open" -> views_open) so every Web API call from listener-injected clients is recorded with canned replies; keep the capture_send_dict patch for response_url. Dispatch helpers: command(), action(action_id, body), interactive_message(callback_id, body), view_submission(callback_id, view, body), event(event). Each form-encodes as Slack does (payload=json for interactions, JSON body for events). Fixture also snapshots and restores the global i18n locale and the i18n load_path side effects so locale tests do not leak across tests.
3. conftest.py: shared edge fakes as fixtures: integrations.sentinel.client.send_event recorder (event names and payloads), incident_drive.list_child_folders (features.incident.drive.adapters.google_drive) returning fixed folders, webhooks.increment_acknowledged_count recorder. No fake of anything inside modules/incident other than the one fan-out seam below.
4. test_legacy_handler_registration_surface.py: one parametrized test per kind asserting the exact registered set from step 1 (6 commands with COMMAND_PREFIX applied, 18 actions, 11 views, 4 events with reaction_added and reaction_removed each registered twice, matcher first then ack-only fallback). Names are literal strings from the inventory so a drift in any later slice or in TASK-26.2 fails loudly. This test covers registration for all 39 rows; per-row behaviour is pinned in each slice.
5. test_incident_declare_surface.py (behaviour, through dispatch only):
   - /incident: ack 200; users_info called for the invoker; views_open of the loading view (callback_id incident_view) with the command trigger_id; views_update on the returned view id with the declare modal (callback_id incident_view, title, locale button value, product options built from the faked Drive folders in name order); French locale when users_info returns fr-FR; command text prefilled into the name block.
   - incident_change_locale: ack; en-US button value renders fr-FR modal and the reverse; views_update targets the body view id; name text and private_metadata preserved.
   - incident_view: valid submission acks, creates the channel (conversations_create with the incident- or incident-dev- prefix and date slug), opens the success modal, logs the incident_called sentinel event, and hands one IncidentPayload to the resource fan-out; source-alert private_metadata resolves chat_getPermalink and failure of the permalink leaves it None; channel creation failure posts the warning to the invoker and does not fan out; fan-out failure posts the warning into the new channel; invalid name (characters, over 59 chars) creates no channel (see latent bug above). The fan-out seam is the single patched name core.initiate_resources_creation in one fixture, recording the payload fields (name, folder, product, security_incident, severity, user_id, channel, source_alert_permalink); its resource-by-resource behaviour is covered by TASK-145.7's own service tests, and TASK-145.7 swaps this one fixture when it deletes modules.incident.core.
   - handle_incident_action_buttons: interactive_message with callback_id handle_incident_action_buttons. call-incident acks, opens the same modal with the alert text as the name and private_metadata carrying source_channel_id and source_message_ts from the body, and logs call_incident_button_pressed. ignore-incident acks, increments the acknowledged count with the button value, calls chat.update (api_call "chat.update") with the buttons attachment removed, only ALLOWED_ATTACHMENT_KEYS kept and the bilingual acknowledgement appended, clears rich_text blocks, and logs ignore_incident_button_pressed.
6. INVENTORY.md: set "Pinned by" for the four rows to the two new test files (with the -k keyword), replace the stale "TASK-38 (after TASK-97)" rebuild ticket with TASK-145.7 on those rows, and reword the "Hard-coded slash commands" intro to mention the new fixture. Leave the other 35 rows "not yet" with their slice ticket.
7. Gates from app/: ruff check ., mypy on touched files, pytest tests/integration/legacy_surface then pytest tests --ignore=tests/smoke.

## AC traceability
AC1 (harness): steps 1-3, exercised by steps 4-5. AC2 (registration set): step 4, test_legacy_handler_registration_surface.py. AC3 (four rows): step 5. AC4 (inventory): step 6. AC5 (gates): step 7.

## Test matrix
Happy: modal open, locale toggle both directions, valid submit, call-incident, ignore-incident. Boundary: name of 59 vs 60 characters, name with a disallowed character, no command text, missing private_metadata. Failure: users_info error falls back to en-US, permalink failure, channel creation failure, fan-out failure. Idempotency and authorization are not part of the legacy surface. Conventions: imports at module top level, fakes only, docstrings describe behaviour, stubs and assertion rationale with no task ids, marked pytestmark = pytest.mark.integration.

## Assumptions and doubts
- Bolt matches app.action("handle_incident_action_buttons") to an interactive_message payload by callback_id. Verify with the first dispatch test before writing the rest.
- Patching WebClient.api_call reaches every listener-injected client, including the one used by say(). Verify that the say() failure test sees the chat_postMessage call.
- create_incident_conversation reads settings.ENVIRONMENT and datetime.now: assert the prefix from the settings object and compute the date in the test instead of freezing time.
- i18n state is global (i18n.set); the fixture restoring it must run for every test that dispatches.
- Registering _register_legacy_handlers alone, without the provider registration, matches production because lifespan calls it with the same Bolt app after the provider has registered its commands; no legacy handler depends on provider-registered ones. Verify with the registration-set test.

## Blast radius and rollback
Tests and one markdown file only; no runtime effect. A revert restores the previous suite. The edit to build_harness is a pure extraction: the existing registration-surface tests must stay green unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Done on this branch (test-only, no production files):
- conftest.py: build_bolt_app shared by both harnesses; RecordingApp also records action, view and event registrations; legacy_handler_harness applies the real _register_legacy_handlers, routes WebClient.api_call into FakeSlackClient (None arguments dropped, as the SDK does), records Sentinel send_event payloads and webhook acknowledged-count increments, fakes the Drive folder listing, and restores the global i18n locale. Docstring now says six hookimpls.
- test_legacy_handler_registration_surface.py pins the 6 commands, 18 actions, 11 views and the 4 reaction listeners (matcher first, then fallback).
- test_incident_declare_surface.py: 23 tests over /incident, incident_change_locale, incident_view and the call-incident/ignore-incident buttons.
- INVENTORY.md: the four rows are pinned and point at TASK-145.7; the remaining rows point at TASK-36.1.2/.3/.4; the stale TASK-38/TASK-97 intro now names TASK-145.

Findings:
- Double ack in submit(): Bolt returns the ack set when its runner first polls, so the errors usually reach Slack (a race, not a guaranteed loss as first noted). The pin asserts the errors body; TASK-145.7 comment corrected.
- Channel names are cut to 80 characters while the slug keeps the full name (pinned with the 59-character case).

Gates (from app/):
- ruff check . -> All checks passed!
- mypy . -> Found 48 errors in 19 files, all in untouched production modules; tests/ is excluded by [tool.mypy] exclude, so 0 in touched files.
- pytest tests --ignore=tests/smoke -> 5044 passed.

The legacy harness also records response_url posts (capture shared with slack_command_harness); the /incident pin asserts none are made. Gates rerun after that change: ruff clean, pytest tests --ignore=tests/smoke -> 5044 passed.
<!-- SECTION:NOTES:END -->
