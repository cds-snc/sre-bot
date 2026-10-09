---
id: TASK-145.4
title: >-
  Carve incident/comms out of scribe: the status-update use case becomes the
  plugin incident.comms
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 19:33'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.3
parent_task_id: TASK-145
priority: high
type: task
ordinal: 354000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A4 of TASK-145. Mechanical move with one visible change: action and callback ids.

THIS SLICE
- features/incident/comms/ in the feature-packages shape: __init__.py (hookimpls register_slack_commands and register_i18n_resources), README.md, settings.py (IncidentStatusUpdateSettings), service.py (from scribe/status_update.py: overview, start, save, generate), approval.py and history.py (from status_update_approval.py and status_update_history.py), prompt.py (from status_update_prompt.py), comms_profile.py, publisher.py (render_copy_ready), domain.py (the status-update types from scribe/domain.py, AI_AUTHOR included), ports.py (TextGenerator, StatusPagePublisher), providers.py (the text generator binding, text_generation_available, the publisher), adapters/text_generation.py and adapters/copy_ready.py, entrypoints/slack.py and slack_views.py (the status-update command, the new, save, generate, review, open, history and published actions, the approve submission), locales/incident_status_update.*.yml.
- Entry point "incident.comms" = "features.incident.comms" in pyproject; action and callback ids become incident.comms.status_update.*; modals open across the deploy are accepted as broken.
- scribe keeps draft and summarize only: its __init__, README, settings, service, domain, ports (IncidentDocumentStore, IncidentReportLinkLookup), providers, adapters/google_docs.py, adapters/slack.py, entrypoints and the two remaining catalogues. Both views modules reach the translator through core.api (TASK-145.2 put the umbrella's single infrastructure.i18n import in core/adapters/i18n.py), so no ignore entry is added or renamed here.
- The incident-umbrella layers contract lists comms beside scribe. Tests move to tests/unit/features/incident/comms/ and tests/integration/features/incident/comms/ with test_incident_comms_* names; mock patch strings rewritten.
- The umbrella README's subdomain table and the legacy_surface inventory rows name comms.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/comms/ is registered as incident.comms and owns every status-update module, catalogue, adapter and test; scribe holds only draft and summarize
- [ ] #2 All status-update action and callback ids start with incident.comms. and no id starting with incident.scribe.status_update remains in code or tests
- [ ] #3 The import-linter ignore list has not grown: the single infrastructure.i18n entry is renamed, the integrations.openai entry is unchanged
- [ ] #4 The umbrella layers contract names comms; the umbrella README and the legacy_surface inventory point status updates at comms
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09); paths assume TASK-145.1 to TASK-145.3 merged. Mechanical move with one visible change: the action and callback ids.

## Discovered state
- Status-update code in features/incident/scribe/: status_update.py, status_update_approval.py, status_update_history.py, status_update_prompt.py, comms_profile.py, publisher.py, adapters/copy_ready.py, adapters/text_generation.py; ports.py holds four Protocols (IncidentDocumentStore and IncidentReportLinkLookup for draft; TextGenerator and StatusPagePublisher for status updates); providers.py holds get_incident_document_store, get_incident_report_link_lookup (draft) and get_status_update_text_generator, text_generation_available, get_status_page_publisher (status updates); settings.py holds IncidentDraftSettings, IncidentSummarySettings, IncidentStatusUpdateSettings; domain.py holds the draft types (DocumentSection, SectionDraft, DocumentField, DraftWriteResult, DraftedDocument) and the status-update types (StatusUpdateOutcomeKind, StatusUpdateDraftOutcome, DraftedFields, NoNewInformationWording, StatusUpdateEdit, CopyReadyText, StatusUpdateOverview, the TASK-145.3 form types, AI_AUTHOR); entrypoints/slack.py registers draft, summarize and status-update (register, 157-247) and the seven block actions and one view submission; slack_views.py holds the draft and summary responses (notify_working, draft_*, summary_*, render_error, to_slack_mrkdwn) and every status-update view; locales/incident_status_update.{en-US,fr-FR}.yml beside incident_draft and incident_summary; __init__.py registers one I18nResourceSpec for the whole locales directory (domain "incident_scribe").
- Tests: 39 status-update test files plus test_incident_scribe_comms_profile_render.py, test_incident_scribe_copy_ready_adapter.py, test_incident_scribe_status_update_publisher.py, test_incident_scribe_text_generation_{adapter,availability}.py under tests/unit/features/incident/scribe/; five dispatch tests under tests/integration/features/incident/scribe/; test_incident_scribe_plugin_registration.py asserts the seven ids under incident.scribe.status_update; tests/unit/server/plugins/test_server_plugins_slack_listener_scoping.py, tests/integration/server/test_lifespan_plugin_loading.py and tests/factories/slack_bolt.py name the plugin incident.scribe.
- pyproject: entry point incident.scribe (45); incident-umbrella layers "documents | drive | meet | scheduling | scribe" (404); ignore entries for scribe: google_docs adapter (303-304), service -> integrations.openai (354); the i18n entry now points at core (TASK-145.2).
- INVENTORY.md row 120 names the status-update handler path; the umbrella README has a subdomain table; the scribe README has the status-update reference section.

## Steps
1. Create features/incident/comms/ in the feature-packages shape: __init__.py (hookimpls register_slack_commands -> entrypoints.slack.register, register_i18n_resources with domain "incident_comms" over comms/locales), README.md (purpose, call path, files, the status-update reference section moved from the scribe README), settings.py (IncidentStatusUpdateSettings and its getter; environment variable names unchanged), service.py (status_update.py), approval.py, history.py, prompt.py, comms_profile.py, publisher.py, domain.py (the status-update types and AI_AUTHOR), ports.py (TextGenerator, StatusPagePublisher), providers.py (text generator binding, text_generation_available, publisher), adapters/{text_generation,copy_ready}.py, entrypoints/slack.py (handle_status_update_command, the seven actions and the submission, register), entrypoints/slack_views.py (status-update views, status_t, build_profile_labels, build_no_new_information_wording; translator from core.api), locales/incident_status_update.*.yml. Use `git mv` for whole-file moves so the diff shows renames.
2. Ids: REVIEW_ACTION_ID and the others become incident.comms.status_update.<suffix>; REVIEW_CALLBACK_ID incident.comms.status_update.approve. Register the entry point "incident.comms" = "features.incident.comms" in pyproject; add comms to the umbrella layers line (siblings stay pipe-separated, exhaustive).
3. scribe keeps draft and summarize: trim __init__ (docstring, no status-update mention), README, settings (two classes), service, domain (draft types only), ports (two Protocols), providers (two getters), adapters/{google_docs,slack}.py, entrypoints (two commands; register loses the action registrations), slack_views (draft and summary responses; its translator import stays through core.api), the two catalogues. No ignore entry changes: the openai and google_docs entries still name scribe modules.
4. Tests: `git mv` the status-update, comms_profile, copy_ready, publisher and text_generation tests to tests/unit/features/incident/comms/ as test_incident_comms_* (status_update prefix kept where it names the use case, e.g. test_incident_comms_status_update_save.py); the five dispatch tests to tests/integration/features/incident/comms/; rewrite imports and patch strings; split test_incident_scribe_plugin_registration.py into a scribe test (two commands, no actions) and test_incident_comms_plugin_registration.py (one command, seven actions, one submission under incident.comms); extend the two server plugin tests and the Bolt factory with the comms plugin name.
5. Docs: umbrella README subdomain table gains comms; INVENTORY.md row 120 points at features/incident/comms/entrypoints/slack.py; decisions/incident-management.md Migration tolerated list: "the scribe subdomain holding three use cases" closes (dated Changes line).

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 (comms owns status updates; scribe only draft and summarize) | 1, 3 | both plugin registration tests; `rg status_update features/incident/scribe` empty |
| 2 (ids start with incident.comms.; none with incident.scribe.status_update) | 2 | test_incident_comms_plugin_registration.py; rg over app/ |
| 3 (ignore list not grown) | 3 | pyproject diff: ignore lines unchanged in count |
| 4 (layers contract, README, inventory) | 2, 5 | lint-imports; review |
| 5 | all | gates |

## Test matrix
Registration: comms registers status-update, seven actions and one submission once each under its prefix; scribe registers draft and summarize and nothing else; both plugins load in the lifespan test. Behaviour: every moved test passes under its new name with no assertion change beyond ids and import paths.

## Assumptions and doubts
- The i18n loader reads every <domain>.<locale>.yml under a registered path, so two directories with distinct domains load independently (scribe/__init__.py docstring); verify no key collision test exists across catalogues.
- Modals open across the deploy carry incident.scribe.status_update.* ids and hit unregistered actions; accepted (as TASK-144.4), deploy in a quiet window.
- If git shows the moves as adds and deletes because of the id edits, make the id rename a separate commit inside the layer so reviewers see pure renames first.

## Size
About 20 files moved, 45 test files moved; new code: comms/__init__.py (~45 lines), README (~80), providers (~25), ports (~40), settings (~30), pyproject (~3). Mechanical.

## Blast radius and rollback
A missed registration leaves a button unhandled; the registration and lifespan tests cover it. Single `git revert`; open modals break either way across the deploy.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Re-ground at pickup (from TASK-145.3): scribe/status_update_form.py is new (start/open/save/fill_status_update_form) and moves with the status-update code (proposed name comms/form.py). The 145.3 form types are StatusUpdateFormState and PublishedRecord in domain.py; StatusUpdateEdit gained blank_fields() and validate_approval_edit is gone; _GENERATE_FAILURE_KEYS, build_saved_form_view and build_filled_form_view are in slack_views.py. The entrypoint and dispatch tests stub on status_update_form, status_update_approval and status_update_history; their monkeypatch targets follow the renamed modules. New tests to move: test_incident_scribe_status_update_{form_save,form_fill,form_view,approval_publish,history_render}.py.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-09 19:17
---
Plan approved
---
<!-- COMMENTS:END -->
