---
id: TASK-140.5.3
title: >-
  Draft from the status-updates modal with a Draft button and show the drafting
  state
status: To Do
assignee: []
created_date: '2026-10-07 16:06'
updated_date: '2026-10-07 16:08'
labels:
  - incident
dependencies:
  - TASK-140.5.2
references:
  - decisions/incident-management.md
  - decisions/platform-entrypoints.md
parent_task_id: TASK-140.5
priority: high
ordinal: 333000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Draft button slice of TASK-140.5 (direction 2026-10-07, decisions/incident-management.md 'Where it happens'). The status-updates modal opened by TASK-140.5.2 gains a Draft button. Opening the modal never starts drafting; only the button does, so opening costs no model call. The button is a native Bolt block-action listener in scribe/entrypoints/slack.py registered through the TASK-140.2 registrar (platform-entrypoints.md rule 3): it acks, shows a drafting state with views.update, calls the TASK-140.5.1 service and then updates the same view with the drafted, carried-forward or pending result rendered in EN and FR by the default comms profile. Nothing is posted to the incident channel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Opening the modal never drafts; pressing Draft acks, shows a drafting state in the same modal, then shows the drafted, carried-forward or pending draft in EN and FR
- [ ] #2 Every service error and every Slack update failure maps to a localized message shown in the modal, never a channel post
- [ ] #3 All new bot strings are in EN and FR catalogues with matching keys
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan 2026-10-07. Layer 4 of Stack H (after TASK-140.5.2); creates scribe/entrypoints/slack.py.

Decisions
- Carried (human): opening the modal never starts drafting; drafting starts only from the Draft button. 140.5.2 renders no button; this layer adds it.
- Human 2026-10-07: loading view first via open_view/update_view (140.5.2); the 140.5.2/140.5.3 split; errors are shown in-modal with a Close button, never in the channel.
- Native Bolt listener in scribe/entrypoints/slack.py registered through the TASK-140.2 registrar with register_block_action (platform-entrypoints.md rule 3); action id incident.scribe.status_update.draft (the scribe entry point is named incident.scribe in pyproject.toml, so the prefix matches). The listener uses Bolt's ack, body and client directly and imports no app/server code.
- t() is called only in scribe/platforms/slack.py; the entry point imports label and view builders from there, and wording for carried-forward updates is built there (NoNewInformationWording).
- Drafting state uses views.update with the view id and hash from body['view']; the result update uses the hash returned by the first update (or none), so a stale hash cannot fail it.
- Channel id and locale travel in the view's private_metadata set by 140.5.2.
- No extra access gate (TASK-129).

Findings
- draft_status_update(conversation_id, *, author, wording, on_started=...) is async, returns OperationResult[StatusUpdateDraftOutcome] with kind DRAFTED, CARRIED_FORWARD or PENDING (scribe/status_update.py:74, domain.py:104-125); on_started fires only before a model call.
- Error codes to map: NOT_AN_INCIDENT, AMBIGUOUS_INCIDENT_CONVERSATION, EMPTY_HISTORY, DRAFT_UNPARSEABLE, STATUS_UPDATE_CONFLICT, classified store and generator errors.
- SlackCommandRegistrar.register_block_action exists (contracts/slack/registrar.py:62); FakeSlackRegistrar.block_actions in tests/factories/slack.py:47 captures listeners.
- Sync Bolt: bridge the async service with asyncio.run, as platforms/slack.py:131 does.

Steps (TDD)
1. scribe/platforms/slack.py: add the Draft button to the pending and no-pending views (action id constant, value carries nothing sensitive); add build_drafting_view(locale), build_result_view(outcome, locale) (EN and FR sections via comms_profile plus a note for carried-forward or pending), build_draft_error_view(error_code, locale) with Close; extend register_commands to also call entrypoints registration, or do it from scribe/__init__.py (decide at implementation: prefer a register_slack_commands hookimpl calling both, no import-time registration).
2. scribe/entrypoints/__init__.py (empty) and scribe/entrypoints/slack.py: register(registrar) and handle_draft_action(ack, body, client): ack first; read view id, hash, user id, private_metadata; views_update to the drafting view; asyncio.run(draft_status_update(channel_id, author=user_id, wording=..., on_started=None)); views_update to the result or error view; Slack API failures logged, never raised.
3. scribe/__init__.py: register the block action in the register_slack_commands hookimpl.
4. locales: add keys for the Draft button, drafting, drafted, carried_forward, pending, empty_history, unparseable, conflict, error, in EN and FR.

AC traceability
- AC1: steps 1-3; tests status_update_entrypoint (ack first, drafting update then result update, three outcomes, no model call on open).
- AC2: steps 1, 2, 4; tests for each error code and Slack update failure.
- AC3: step 4; locale parity test.
- AC4: gates.

Test matrix (tests/unit/packages/incident/scribe/, matching existing naming)
- test_incident_scribe_status_update_entrypoint.py: ack called before any other call; drafting view sent with view id and hash; result view per outcome kind (drafted, carried forward, pending) in EN and FR; each error code maps to a localized in-modal error with Close; views_update failure on the drafting update (logged, still drafts or stops cleanly: assert chosen behavior), failure on the result update (logged); service stubbed through the injected generator and in-memory store (InMemoryStatusUpdateStore); no post_message or post_ephemeral calls; repeated press with a pending draft makes no second model call.
- test_incident_scribe_status_update_slack.py (edit the 140.5.2 file in place): Draft button present in pending and no-pending views, absent in error views.
- test_incident_scribe_status_update_locales.py (edit in place): parity for the new keys.
- test_incident_scribe_plugin_registration.py (edit in place): the block action id is registered once with the plugin prefix.
- Opening the modal (140.5.2 tests) asserts the generator is never called.

Assumptions to verify
- The Draft button's block_actions body includes view.id and view.hash for a modal button (Slack docs; check with a captured fixture in the test).
- views.update must complete within the modal's lifetime; the drafting call can run up to a minute while Bolt's ack is already sent.

Size gate: about 6 production files (platforms/slack.py, entrypoints/__init__.py, entrypoints/slack.py, scribe/__init__.py, 2 locale files), about 160 production LOC plus about 30 YAML lines; one subsystem. Within the gate.

Blast radius and rollback: single revert removes the button and listener, leaving the 140.5.2 read-only modal. Drafts are stored by 140.5.1 and survive. Requires TASK-140.2 registrar (already in the stack) and the status-update table from TASK-140.4 applied before deploy.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 16:08
---
Plan approved by the human 2026-10-07. Implement after TASK-140.5.2 on layer 4 (stack-h/task-140.5.3-status-update-draft-button).
---
<!-- COMMENTS:END -->
