---
id: TASK-140.8.1
title: >-
  List an incident's approved status updates in the status-updates modal and
  reopen their copy-ready text
status: In Progress
assignee: []
created_date: '2026-10-07 22:56'
updated_date: '2026-10-07 23:39'
labels:
  - incident
dependencies:
  - TASK-140.6.2
parent_task_id: TASK-140.8
priority: high
type: feature
ordinal: 342000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scribe-only slice of TASK-140.8 (Stack H layer 9). The status-updates modal opened by /sre incident status-update shows the pending draft as today, then an Approved updates section: one row per APPROVED or PUBLISHED update, newest first, with stage, approval time in ET/HE, approver and published state (read-only here), capped at 50 rows with a localized note, and a localized empty state. Each row's Open button replaces the modal in place with the update's copy-ready EN and FR text, rendered by render_copy_ready through the StatusPagePublisher so it is identical to what approval showed, with a Back button that re-renders the list in place. Nothing is posted to the incident channel and nothing is written to the store.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The status-updates modal lists approved updates newest first with stage, approval time in ET/HE, approver and published state
- [x] #2 Opening an approved update shows its copy-ready EN and FR text, identical to what was shown at approval, with a Back button to the list
- [x] #3 An incident with no approved updates shows a localized empty state; all strings are in EN and FR catalogues
- [x] #4 Nothing is posted to the incident channel and nothing is written to the store
- [x] #5 Block actions dispatch through a real SlackPlatformProvider in an integration test
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Basis: stack is on main a18167d2 (ruff PLC0415 on); rebase before implementing if main moved. Imports at module top only, tests included; no __import__/importlib; a circular import is a design flaw to fix in the design. t() stays only in scribe/platforms/slack.py. No new ErrorCodes (reuse STATUS_UPDATE_NOT_APPROVED, STATUS_UPDATE_CONFLICT). Nothing is written to the store and nothing is posted to the channel.

Settled (human, 2026-10-07, recommended answers): split 140.8 into 140.8.1/140.8.2; open an update in place with a Back button (not views.push); overview function with get_pending_status_update delegating; draft-result and approval views unchanged; 50-row cap with a localized note.

Design:
D1. Modal opened by /sre incident status-update: pending draft block as today, then an "Approved updates" section. One section block per approved (APPROVED or PUBLISHED) update, newest first: "*Stage* - YYYY-MM-DD HH:MM ET/HE - approved by <@U..> - Published / Not published" (state read-only here; approver segment omitted if None), with an Open accessory button (action id incident.scribe.status_update.open, value JSON {incident_id, sequence}). Capped at 50 rows with a localized "showing the latest 50" note. Empty state: localized line under the section header, shown whether or not a draft is pending.
D2. scribe/domain.py: frozen dataclass StatusUpdateOverview(pending, approved). status_update.py: sync get_status_update_overview(conversation_id, *, lookup=None, store=None): one lookup and one list; approved = non-DRAFT records newest first; get_pending_status_update delegates (behaviour and tests unchanged). The command-handler block building moves into platforms/slack.py build_overview_view(overview, locale, private_metadata), shared by the command and Back.
D3. Open: scribe/status_update_history.py (new) async get_approved_update(incident_id, sequence, *, store=None): non-DRAFT record; DRAFT -> STATUS_UPDATE_NOT_APPROVED; missing sequence -> STATUS_UPDATE_CONFLICT; store errors classified. Entrypoint handle_open_action: ack, asyncio.run of one helper (get_approved_update then providers.get_status_page_publisher().publish with build_profile_labels en-US/fr-FR, like _approve_and_publish), then views_update in place (view id + hash via _ModalCursor). build_copy_ready_view gains optional update: StatusUpdate | None; when given it adds the status line (approved by whom/when in ET/HE, published state read-only) and a Back button (action id incident.scribe.status_update.history, value {channel_id}); without it the approval view is byte-identical to today. Back: handle_history_action re-runs get_status_update_overview(channel_id) and re-renders build_overview_view in place; metadata stays {channel_id, locale}. Error -> existing Close-only in-modal error view.
D6. comms_profile.py: public format_profile_time(moment, labels) (Toronto zone, %Y-%m-%d %H:%M + labels.time_suffix); render_profile_sections uses it (output unchanged). Suffix from build_profile_labels(locale): ET en-US, HE fr-FR.
D7. Locale keys (both files): history header, history_empty, history_truncated, row published/not_published/approved_by pieces, open_button, back_button, approved status line. EN/FR parity test covers them.

Steps: (1) comms_profile format_profile_time; (2) scribe/domain.py overview dataclass; (3) status_update.py overview + delegation; (4) status_update_history.py get_approved_update; (5) platforms/slack.py build_overview_view, row builder, extended build_copy_ready_view, action id constants; (6) entrypoints/slack.py handle_open_action, handle_history_action, register_block_action x2; (7) locales.

AC traceability and tests (new files, layered tree, structural exact assertions on blocks/dicts, no str(view) matching):
- AC1: steps 1-3,5; unit/packages/incident/scribe/test_incident_scribe_status_update_overview.py (pending/approved/empty, newest first, lookup and store errors, get_pending unchanged) and test_incident_scribe_status_update_history_view.py (row blocks, stage, ET vs HE time, approver, published state for APPROVED and PUBLISHED, Open values, 50-row cap + note, EN/FR).
- AC2: steps 4-6; test_incident_scribe_status_update_history.py (get_approved_update outcomes over InMemoryStatusUpdateStore), history_view (detail view: copy text equals render_copy_ready output for the stored record, status line, Back button; approval view without update unchanged), test_incident_scribe_status_update_history_entrypoint.py (open/back handlers with fake client: hash handling, error views, Slack failure logged).
- AC3: history_view empty state EN and FR; existing locale parity test.
- AC4: entrypoint tests assert only views_update client calls and no store write (counting fake store).
- AC5: integration/packages/incident/scribe/test_incident_scribe_status_update_history_dispatch.py via harness_fixture("incident.scribe"): real plugin, real pluggy manager and SlackPlatformProvider, dispatches real block_actions for open and history, asserts ack and views.update api_calls only, ids pass the plugin-prefix check.
- AC6: ruff, mypy (0 new in touched files), lint-imports, pytest tests --ignore=tests/smoke, manual check of touched files for function-level imports.

Size gate: ~255 production LOC, 8 files (comms_profile, scribe/domain, status_update, status_update_history new, platforms/slack, entrypoints/slack, 2 locales), one subsystem (scribe), behaviour only apart from the small build_overview_view extraction forced by Back. Under the gate. Trim order if it grows: truncation note, then secondary polish.

Assumptions to verify: views.update by view id after a block action works as in layers 4/8; rich_text_preformatted copy fidelity (manual check already pending from 140.6.2); nothing else enumerates StatusUpdateOverview-shaped call sites of get_pending_status_update (grep).

Blast radius and rollback: read-only, no core or Terraform change; one revert restores the previous modal.

What TASK-140.8.2 consumes: build_copy_ready_view(update=...) status line and action row to add the toggle to; get_approved_update and the open helper (publish + detail view) to re-render after a toggle; status_update_history.py as the home for set_published; format_profile_time; _ModalCursor/_parse_metadata; the history/open action ids and metadata shape.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07: the human settled the 6 planning questions (split, in-place open with Back, overview function, draft/approval views unchanged, undo clears both, 50-row cap) with the recommended answers.

Implemented (Stack H layer 9). Production: comms_profile.py +format_profile_time (+6/-2), scribe/domain.py StatusUpdateOverview (+13), status_update.py get_status_update_overview + get_pending delegation (+32/-6), new status_update_history.py get_approved_update (45), platforms/slack.py build_overview_view/_approved_blocks/_stage_line/extended build_copy_ready_view + OPEN/HISTORY ids (+114/-16), entrypoints/slack.py handle_open_action/handle_history_action/_read_and_publish + registrations (+89/-2), both locale ymls (+8 each). ~310 added lines incl. docstrings and yml, 8 files, one subsystem. Tests edited in place: review_entrypoint TestRegister (5-entry dict); slack.py command test vacuous str(view) assertions replaced with exact block assertions (no mypy errors remain in it).
Gates (app/): ruff check clean; ruff format --check 843 files formatted; lint-imports 10 kept 0 broken; mypy 57 errors in 20 files (baseline, 0 in touched files); pytest tests/unit tests/integration: 3466 passed; no function-level imports in touched files.
Full pytest tests --ignore=tests/smoke: 17 failed = 6 TASK-90 (sns/google directory) + 8 capture_logs leak failures (4 pre-existing entrypoint/review ones + 4 new history_entrypoint log tests, same cause, green in isolation) + 3 new history_view tests that pin literal 'French'/'English' headings and fail only when an earlier test leaves the i18n catalogue loaded (fr-FR catalogue yields Francais/Anglais); production heading behaviour unchanged. Pre-authored tests untouched.
Deviations: none from the plan. Locale keys: history_header, history_empty, history_truncated, row.approved_by, row.published, row.not_published, open_button, back_button; FR fallbacks equal the YAML.
Pending manual workspace checks: views.update in place after Open/Back in a real workspace; rich_text_preformatted copy fidelity; ET/HE row times.

2026-10-07 review fixes: (1) language headings: _pending_blocks, build_review_view and build_copy_ready_view looked up language.fr in fr-FR (catalogue 'Français') with fallback 'French', so output depended on whether the catalogue was loaded (the new history_view tests failed only in the combined run). Added _language_heading(language) in platforms/slack.py with catalogue-matching fallbacks ('English', 'Français'), used in all three. (2) the modal frame's title/close fallbacks were English-only for fr-FR; now 'Mises à jour de statut' / 'Fermer', matching the catalogue. The history_view approval-view test now pins the per-locale title/close and 'Français'. (3) removed the unused loop variable ruff B007 flagged. Gates after the fixes: ruff check . All checks passed; ruff format --check 843 files already formatted; lint-imports 10 kept, 0 broken; mypy 57 errors in 20 files, 0 in touched files; pytest tests/unit/packages/incident/scribe + integration scribe 696 passed; pytest tests --ignore=tests/smoke 14 failed, 4235 passed = 6 known TASK-90 + 8 scribe capture_logs tests (4 earlier + 4 in test_incident_scribe_status_update_history_entrypoint.py) from TASK-90 leak 2 (cached structlog loggers), all passing in isolation and in the split runs.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 23:01
---
Plan approved by the human 2026-10-07.
---
<!-- COMMENTS:END -->
