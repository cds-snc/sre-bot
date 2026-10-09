---
id: TASK-144.1
title: >-
  Merge scribe's platforms/slack.py into entrypoints/: one Slack entry-point
  module and one views module
status: To Do
assignee: []
created_date: '2026-10-09 12:53'
updated_date: '2026-10-09 13:01'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/feature-packages.md
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
parent_task_id: TASK-144
priority: high
type: chore
ordinal: 345000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 1 of TASK-144 (mechanical, no behaviour change). decisions/feature-packages.md has one entrypoints/ directory for every inbound handler and lists platforms/ as drift to be renamed; platform-entrypoints.md rule 3 and transport-slack.md name entrypoints/slack.py as the file holding commands, block actions and view submissions. packages/incident/scribe is the only package with both: platforms/slack.py (the three /sre incident commands plus every Block Kit builder, parser and translated wording) predates the rename, and TASK-140.2 added entrypoints/slack.py beside it for the block actions and the view submission. The hookimpl in scribe/__init__.py calls both registration functions.

TARGET: scribe/entrypoints/slack.py holds every handler (the three command handlers and their argument parsing, the block-action and view-submission listeners) and one register(registrar) function; scribe/entrypoints/slack_views.py holds the view builders, payload parsers, action-id constants and every translated string, and is the only scribe module importing infrastructure.i18n. platforms/ is deleted. The import-linter ignore entry for infrastructure.i18n is renamed to the views module, never duplicated (migration.md rule 3: ignore lists never gain entries), which is why the two remaining t() calls inside handle_summarize_command move into a views helper.

Every test import and unittest.mock patch string naming packages.incident.scribe.platforms is rewritten (about 25 files under tests/unit/packages/incident/scribe and tests/integration/packages/incident/scribe); the three legacy_surface INVENTORY.md rows for the scribe commands and the scribe README point at the new module. No command name, modal, reply or log event changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident/scribe/platforms/ no longer exists; entrypoints/slack.py holds the command, block-action and view-submission handlers and one register() function; entrypoints/slack_views.py holds the builders, parsers, action ids and wording and is the only scribe module importing infrastructure.i18n
- [ ] #2 scribe/__init__.py's register_slack_commands hookimpl calls one registration function; the plugin-registration test asserts the same commands, block actions and view submission as before
- [ ] #3 rg finds no 'scribe.platforms' under app/ (code, tests, pyproject.toml, INVENTORY.md, README); the import-linter ignore entry is renamed, not added, and lint-imports passes
- [ ] #4 Every existing scribe test passes with only import paths and patch strings changed; no assertion changes
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main af6a316e (2026-10-09). Line numbers below are from that commit; re-run the greps before editing.

## Discovered state

- `app/packages/incident/scribe/platforms/slack.py` (1,160 lines): constants at lines 65-118 (`_DRAFT_DOMAIN`, `_SUMMARY_DOMAIN`, `_STATUS_UPDATE_DOMAIN`, `_SLACK_TEXT_LIMIT`, the eight action ids `DRAFT_ACTION_ID` ... `WRITE_ACTION_ID`, `_APPROVED_ROW_CAP`, `_SECURITY_CONFIRMED`, `_REDRAFT_NOTICES_EN/FR`, `_TEXT_FIELDS`, `_SINCE_UNITS`, `_SLACK_FORMAT_INSTRUCTIONS`); `register_commands` (120); command handlers `handle_draft_command` (203), `handle_summarize_command` (380), `handle_status_update_command` (545); draft and summarize renderers `_notify_working` (260), `_success_response` (283), `_render_error` (315), `_draft_error_response` (370), `_to_slack_mrkdwn` (491), `_summary_error_response` (535); argument parsers `_parse_limit` (360), `_parse_since` (453), `_parse_since_seconds` (465); status-update wording, builders and parsers from `_status_t` (605) to `build_no_new_information_wording` (1159), including `_status_update_open_failed` (628).
- `t()` from `infrastructure.i18n` is called at lines 272, 292, 302, 310, 323, 330, 337, 344, 372, 421, 423, 438, 537, 606. Lines 421, 423 and 438 are inside `handle_summarize_command` (the result header, the disclaimer and one error text); every other call is inside a renderer or `_status_t`.
- `app/packages/incident/scribe/entrypoints/slack.py` (about 580 lines): block-action and view-submission listeners, `register(registrar)`, `_ModalCursor`, `_run_draft`, `_manual_review_view`; imports every builder and constant from `platforms.slack`.
- `app/packages/incident/scribe/__init__.py`: `register_slack_commands` calls `slack.register_commands(registrar)` then `slack_entrypoints.register(registrar)`.
- `app/pyproject.toml:305`: import-linter ignore `"packages.incident.scribe.platforms.slack -> infrastructure.i18n"`; the umbrella layers contract at line 404 names `scribe` only, no submodule.
- Importers of `packages.incident.scribe.platforms` outside the package (rg at af6a316e): none in production code. Tests: `tests/unit/packages/incident/scribe/` test_incident_scribe_draft_slack.py (patch string `_DRAFT`), test_incident_scribe_summary_slack.py (`_SUMMARIZE`, `_HANDLE`), test_incident_scribe_status_update_slack.py (12 patches of `platforms.slack.get_status_update_overview`), test_incident_scribe_status_update_dispatch.py (patch of `handle_status_update_command`), test_incident_scribe_status_update_{history,published,review,redraft,manual}_entrypoint.py, test_incident_scribe_status_update_{history,published,review,redraft,manual}_view.py, test_incident_scribe_status_update_confirmation.py, test_incident_scribe_plugin_registration.py; `tests/integration/packages/incident/scribe/` test_incident_scribe_status_update_{history,published,review,redraft}_dispatch.py. Re-list with `rg -l 'scribe\.platforms' app/tests`.
- `app/tests/integration/legacy_surface/INVENTORY.md` rows 118-120 point at `platforms/slack.py:117`, `:136`, `:161`. `app/packages/incident/scribe/README.md` "Files" section (lines 55-108) lists `platforms/slack.py`.

## Decision taken in this plan

One handler module and one views module, both under `entrypoints/`. A single 1,700-line `slack.py` would be unreviewable later, and the records constrain the directory, not the number of modules in it (feature-packages.md layout table; platform-entrypoints.md Checks constrain `slack_bolt`/`slack_sdk` to `entrypoints/slack.py` and `adapters/`, which the views module imports neither of). Every translated string lives in the views module so the single import-linter ignore entry is renamed, never duplicated (migration.md rule 3).

## Steps

1. Create `app/packages/incident/scribe/entrypoints/slack_views.py` by moving, unchanged except for names, from `platforms/slack.py`: the constants block (65-118 except `_SINCE_UNITS`), the renderers `_notify_working`, `_success_response`, `_render_error`, `_draft_error_response`, `_to_slack_mrkdwn`, `_summary_error_response`, `_status_update_open_failed`, and everything from `_status_t` (605) to the end. Add `summary_success_response(body: str, locale: str) -> CommandResponse` holding lines 421-438's header, disclaimer and blocks, and `summary_text(key, locale, fallback)` for the remaining `t()` call in `handle_summarize_command`. Drop the leading underscore on every name the handler module needs: `status_t`, `status_error_text`, `status_update_open_failed`, `status_update_view`, `mrkdwn_blocks`, `notify_working`, `draft_success_response` (was `_success_response`), `render_error`, `draft_error_response`, `to_slack_mrkdwn`, `summary_error_response`, `DRAFT_DOMAIN`, `SUMMARY_DOMAIN`, `SLACK_FORMAT_INSTRUCTIONS`, `SLACK_TEXT_LIMIT`. Module docstring: "Block Kit views, payload parsers and wording for the incident scribe Slack entry point; the only scribe module that translates."
2. In `entrypoints/slack.py`: add the three command handlers, `_parse_limit`, `_parse_since`, `_parse_since_seconds` and `_SINCE_UNITS`; fold the body of `register_commands` into `register(registrar)` (the nested `_dispatch_*` closures and three `register_command` calls first, then the existing `register_block_action` and `register_view_submission` calls). Replace the `from packages.incident.scribe.platforms.slack import (...)` block with imports from `packages.incident.scribe.entrypoints.slack_views`. Update the module docstring to cover commands.
3. `scribe/__init__.py`: import `from packages.incident.scribe.entrypoints import slack`; `register_slack_commands` calls `slack.register(registrar)` only; docstring names the three subcommands and the modal.
4. Delete `app/packages/incident/scribe/platforms/__init__.py` and `platforms/slack.py`.
5. `app/pyproject.toml:305` becomes `"packages.incident.scribe.entrypoints.slack_views -> infrastructure.i18n"`. Run `cd app && uv run lint-imports`; the ignore list has the same number of entries.
6. Rewrite the test imports and patch strings listed above. Rule: handler names (`handle_*_command`, `register`, `handle_*_action`, `handle_review_submission`) come from `entrypoints.slack`; builders, parsers and action ids from `entrypoints.slack_views`; a patch string targets the module that looks the name up, so `patch("packages.incident.scribe.platforms.slack.get_status_update_overview")` becomes `patch("packages.incident.scribe.entrypoints.slack.get_status_update_overview")` and `_DRAFT`/`_SUMMARIZE` likewise. The registration test's expected sets are unchanged; add one assertion that `register_slack_commands` registers the `status-update` command and the view submission through the single `register`.
7. `INVENTORY.md` rows 118-120: path `packages/incident/scribe/entrypoints/slack.py:<line of each register_command call>`. README "Files": replace the `platforms/slack.py` row with `entrypoints/slack.py` and `entrypoints/slack_views.py`; `rg -n platforms app/packages/incident/scribe/README.md` must come back empty.
8. Verify: `rg -n 'scribe\.platforms|scribe/platforms' app` empty; `cd app && uv run python -c 'import packages.incident.scribe'`; the def count moved equals the def count removed plus two helpers (`grep -c '^def ' ` on the three files before and after).

## AC traceability

| AC | Steps | Evidence |
| --- | --- | --- |
| 1 | 1, 2, 4 | tree listing; `rg -n 'infrastructure.i18n' app/packages/incident/scribe` lists `entrypoints/slack_views.py` only |
| 2 | 3, 6 | test_incident_scribe_plugin_registration.py |
| 3 | 5, 7, 8 | `rg` empty; `uv run lint-imports` output; `git diff app/pyproject.toml` shows one line changed |
| 4 | 6 | full scribe suite green; `git diff --stat app/tests` shows import and patch lines only |
| 5 | all | gate commands and output in the notes |

## Test matrix

No new behaviour, so no new behaviour tests. Existing: command dispatch (draft, summarize, status-update), every status-update entrypoint and view test, the four integration dispatch tests, registration, locales parity. One added assertion in the registration test (step 6).

## Assumptions and doubts

- No production module outside scribe imports `scribe.platforms` (verified by rg at af6a316e; re-run).
- The umbrella import-linter contract does not name `platforms` or `entrypoints` submodules (pyproject.toml:404 verified).
- Tests that patch builders on `entrypoints.slack` (if any) stay valid because the handler module still imports those names; check with `rg 'entrypoints\.slack\.' app/tests`.
- `slack_views.py` imports neither `slack_bolt` nor `slack_sdk` (verify with rg after the move) so platform-entrypoints.md's Checks hold.

## Size and review

Moved: about 1,160 lines out of `platforms/slack.py` into two files; net new code under 40 lines (two summarize helpers, the merged `register`). Production files: 2 created or changed, 2 deleted, `__init__.py`, `pyproject.toml`, README, INVENTORY. Tests: about 25 files, import and patch lines only. Mechanical PR reviewed for completeness: reviewers compare the function inventory of the deleted file with the two new ones.

## Blast radius and rollback

A missed import or patch string fails at import or patch time; the registration test and the import check in step 8 catch the former, pytest the latter. A plugin import error aborts boot (TASK-110), so this cannot ship half-working. Single `git revert` restores the previous layout. No data, config or Terraform change.
<!-- SECTION:PLAN:END -->
