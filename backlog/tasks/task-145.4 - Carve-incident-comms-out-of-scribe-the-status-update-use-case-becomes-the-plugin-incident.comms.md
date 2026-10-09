---
id: TASK-145.4
title: >-
  Carve incident/comms out of scribe: the status-update use case becomes the
  plugin incident.comms
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
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
- scribe keeps draft and summarize only: its __init__, README, settings, service, domain, ports (IncidentDocumentStore, IncidentReportLinkLookup), providers, adapters/google_docs.py, adapters/slack.py, entrypoints and the two remaining catalogues. The import-linter ignore entry for infrastructure.i18n moves with the views module that imports it (one entry, not two): either the scribe views stop importing it or the entry is renamed to comms.
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
