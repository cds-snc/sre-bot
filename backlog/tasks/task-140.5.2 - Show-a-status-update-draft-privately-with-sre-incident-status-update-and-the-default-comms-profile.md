---
id: TASK-140.5.2
title: >-
  Open the incident's status-updates modal with /sre incident status-update and
  show the pending draft with the default comms profile
status: Done
assignee: []
created_date: '2026-10-07 14:55'
updated_date: '2026-10-08 15:49'
labels:
  - incident
dependencies:
  - TASK-140.5.1
parent_task_id: TASK-140.5
priority: high
type: feature
ordinal: 330000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Command and modal-open slice of TASK-140.5 (direction 2026-10-07, decisions/incident-management.md 'Where it happens'). /sre incident status-update opens the incident's status-updates modal, private to the invoker; no status-update text is ever posted to the incident channel. The command opens a loading view at once with the command's trigger id (it expires after about 3s), then resolves the incident, reads the pending draft and updates the view to it, rendered by the default comms profile (scribe/comms_profile.py, modelled on GC Notify's published incident history) in EN and FR, or to a localized no-pending-draft or error view. Outside an incident channel the view becomes a localized refusal with a Close button. Opening never drafts; the Draft button and the drafting state are TASK-140.5.3. Later layers add review and approval (TASK-140.6), the approved history (TASK-140.8) and redrafting (TASK-140.9). The same modal is later reached from the central incident modal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 In an incident channel the command opens the incident's status-updates modal, visible only to the invoker, and nothing is posted to the channel
- [x] #2 The profile shows stage, affected service, impact, current action, workaround and the next update time in America/Toronto as YYYY-MM-DD HH:MM ET (EN) or HE (FR), and omits the next update line when the stage is resolved
- [x] #3 Outside an incident channel the command refuses with a localized message, and every error maps to a localized message
- [x] #4 All bot strings are in EN and FR catalogues with matching keys
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-plan 2026-10-07 (supersedes the ephemeral-preview plan). Layer 3 of Stack H; the Draft button and drafting state moved to TASK-140.5.3.

Decisions
- Carried: the default comms profile lives here so the draft view and the later copy-ready text match; time is America/Toronto as YYYY-MM-DD HH:MM ET (EN) or HE (FR); a resolved stage omits the next update line; stored EN and FR text use fixed en-US and fr-FR lookups; t() is called only in scribe/platforms/slack.py; no extra access gate (TASK-129).
- Carried (human): opening the modal never starts drafting; drafting starts only from the Draft button (TASK-140.5.3). This layer renders no Draft button, so nothing inert ships.
- Human 2026-10-07: open a loading view first with the command's trigger id, then update it. SlackReplySender.open_view returns the view id and a new update_view is added (contract, provider, FakeSlackReply).
- Human 2026-10-07: the 140.5.2/140.5.3 split.
- Human 2026-10-07: outside an incident channel, and on any error, the loading view is updated to an in-modal localized error view with a Close button; no ephemeral or channel post.
- Parent command: scribe registers with parent="sre.incident" like draft and summarize; the provider auto-creates intermediate nodes (integrations/slack/provider.py:383-410) and legacy /sre incident is registered by modules.sre, so no extra parent registration is needed. The registration test asserts the parent.

Findings (call sites)
- comms_profile.py does not exist; 140.5.1 did not create it. Created here.
- CommandPayload has no trigger_id; read payload.platform_metadata["trigger_id"] (precedent: packages/user_rotations/platforms/slack.py:73).
- contracts/slack/reply.py:33 open_view returns OperationResult[None]; integrations/slack/provider.py:73-98 _call discards the response; tests/factories/slack.py FakeSlackReply:33 records open_view. Only user_rotations calls open_view and ignores the data.
- core/api.py exports IncidentLookup (get_incident_lookup:148), StatusUpdateStore.list_for_incident (newest first, :124), get_status_update_store (:159).
- scribe/domain.py has StatusUpdateOutcomeKind and NoNewInformationWording; status_update.py draft_status_update is async (used by 140.5.3).

Steps (TDD, each test first)
1. contracts/slack/reply.py, integrations/slack/provider.py: open_view returns OperationResult[str] (view id in data, error if the response has none); add update_view(*, view_id, view, hash=None) -> OperationResult[None]. Update FakeSlackReply (returns a canned view id, records update_view). Mechanical, behavior-preserving for user_rotations.
2. scribe/comms_profile.py: frozen ProfileLabels (stage labels, field labels, next-update label, time suffix) and render_profile(text, stage, next_update_at, labels) -> str. Pure, no t(), no Slack SDK; omits the next update line when stage is RESOLVED.
3. scribe/status_update.py: get_pending_status_update(conversation_id, *, lookup=None, store=None) -> OperationResult[StatusUpdate | None]: lookup, list_for_incident, the latest record when its state is DRAFT, else None. Failures pass through classified.
4. scribe/platforms/slack.py: handle_status_update_command(payload, parsed_args, reply): trigger id check; open loading view (private_metadata carries channel id and locale); call get_pending_status_update (a plain sync call, no asyncio needed); update_view to the pending view (EN and FR sections rendered with comms_profile, split per language, each block under 3000 chars) or the no-pending view or the error view. build_profile_labels(locale) builds the labels with t() for fixed en-US and fr-FR lookups, so both languages render regardless of the invoker's locale. Error mapping: NOT_AN_INCIDENT, AMBIGUOUS_INCIDENT_CONVERSATION, store errors, open_view failure (ephemeral localized CommandResponse, since no view exists), update_view failure (logged, loading view left). register_commands adds status-update under sre.incident.
5. locales: incident_status_update.en-US.yml and .fr-FR.yml (title, close, loading, no_pending, stage and field labels, ET/HE suffix, not_an_incident, ambiguous, error, open_failed, description, examples) with matching keys.
6. README of scribe: one paragraph on the command. No entry-point change; scribe/__init__.py already calls slack.register_commands.

AC traceability
- AC1: steps 1, 3, 4; tests status_update_slack (opens loading view first, nothing posted).
- AC2: step 2; tests comms_profile_render.
- AC3: steps 4, 5; tests status_update_slack error cases.
- AC4: step 5; tests status_update_locales parity and no hardcoded strings outside slack.py.
- AC5: gates.

Test matrix (new files under tests/unit/packages/incident/scribe/, naming per the existing test_incident_scribe_<entity>_<action>.py files)
- test_incident_scribe_comms_profile_render.py: every stage, resolved omits next line, ET/HE suffix, Toronto conversion across a DST boundary, EN and FR labels.
- test_incident_scribe_status_update_pending.py: draft latest returned, approved latest gives None, no records gives None, not-an-incident, ambiguous, store failure.
- test_incident_scribe_status_update_slack.py: loading view opened before any lookup (call order via FakeSlackReply), pending view in EN and FR, no-pending view, no trigger id, outside an incident channel (error view with Close), ambiguous, store error, open_view failure, update_view failure, registration under sre.incident, no post_message or post_ephemeral calls.
- test_incident_scribe_status_update_locales.py: EN/FR key parity.
- tests/unit/integrations/slack/test_slack_provider_reply_views.py: open_view returns the id, missing id and Slack error classified, update_view passes view id and hash.
- Edit in place tests/unit/packages/incident/scribe/test_incident_scribe_plugin_registration.py if it enumerates registered commands.

Assumptions to verify
- Slack views.open response carries view.id (confirm in slack_sdk response shape in the provider test).
- The legacy-table scan finishes well after the 3s trigger window can lapse; that is why the loading view opens first. Verify the loading view is the first reply call.
- Legacy /sre incident help is unaffected by the new child (run tests/integration/legacy_surface/test_slack_command_registration_surface.py).
- Locale loader reads any <domain>.<locale>.yml under scribe/locales (scribe/__init__.py registers the directory once).

Size gate: about 8 production files (reply.py, provider.py, comms_profile.py, status_update.py, platforms/slack.py, 2 locale files, README), about 270 production LOC plus about 80 YAML lines; one subsystem pair (scribe plus the Slack contract, a small mechanical change). Within ~400 LOC and ~10 files.

Blast radius and rollback: a single revert restores service; the only shared change is open_view's return type, ignored by its one other caller. The command is new, no data is written, no ordering constraint beyond 140.5.1 (service and stores) being merged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation (2026-10-07).
Files: contracts/slack/reply.py (open_view returns the view id; update_view added), integrations/slack/provider.py (_request keeps the response; open_view reads view.id, MISSING_VIEW_ID when absent; update_view), contracts/operations/codes.py (MISSING_VIEW_ID registered), scribe/comms_profile.py (new, pure), scribe/status_update.py (get_pending_status_update), scribe/platforms/slack.py (handle_status_update_command, build_profile_labels, registration under sre.incident), locales incident_status_update.{en-US,fr-FR}.yml, scribe README section.
Test edits in place (contract change, not weakening): test_slack_provider_reply_classifies_errors open_view test now returns a view id; tests/factories/slack_bolt.py FakeSlackClient has a canned views_open reply with view.id; legacy_surface registration test pins the new sre.incident.status-update node and its rotations view test passes again; scribe plugin registration test enumerates status-update and the new locale domain.
Gates (from app/): ruff check . -> All checks passed. mypy . (excluding .venv) -> 57 errors in 20 files, all pre-existing in untouched files (modules/*, integrations/slack/channels.py etc.); 0 in touched files. lint-imports -> Contracts: 10 kept, 0 broken. pytest tests --ignore=tests/smoke -> 6 failed, 3894 passed; the 6 are the known TASK-90 order leaks (3 tests/modules/webhooks/test_webhooks_aws_sns.py, 3 tests/unit/infrastructure/directory/test_google.py), unrelated to this change. tests/integration/legacy_surface/test_slack_command_registration_surface.py -> 20 passed.
Deviation: none from the plan beyond the registered MISSING_VIEW_ID code and the in-place test edits above. TASK-140.5 ACs: none newly checkable by 140.5.2 alone (AC2-4 already checked; AC1, AC5, AC6 also need 140.5.3), so none were checked.

Fixed 2026-10-07 after local testing: status-update was registered with arguments=[], which the provider treats as no arguments, so it called the handler with the payload only; the registered handler required parsed_args and every call failed. Now one payload-only dispatcher with no arguments or fallback. New test_incident_scribe_status_update_dispatch.py routes the command through a real SlackPlatformProvider.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Plan approved by the human 2026-10-07 (all recommended decisions, including the 140.5.1/140.5.2 split). Clarified: nothing is ever pushed automatically; approved EN and FR text is proofread and copied by hand into whatever system the product team uses.
---

created: 2026-10-07 15:17
---
2026-10-07: the approved plan is superseded. The human moved drafting, review and history into modals (no status-update text in the incident channel), so the command now opens the status-updates modal instead of replying with an ephemeral preview. Title, description and ACs updated; re-plan before implementation.
---

created: 2026-10-07 16:08
---
Plan approved by the human 2026-10-07 (re-plan: loading view then update_view, 140.5.2/140.5.3 split, in-modal error view). The Slack contract change (open_view returns the view id, new update_view) stays in this layer by human decision: about 30 LOC whose only consumer is this layer.
---
<!-- COMMENTS:END -->
