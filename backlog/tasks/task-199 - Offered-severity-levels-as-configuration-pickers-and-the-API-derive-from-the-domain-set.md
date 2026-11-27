---
id: TASK-199
title: >-
  Offered severity levels as configuration: pickers and the API derive from the
  domain set
status: To Do
assignee: []
created_date: '2026-11-27T18:25:00Z'
labels:
  - incident
  - configuration
dependencies:
  - TASK-145.7.10
priority: low
ordinal: 552000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The severity scale is a closed domain set in features/incident/common/vocabulary.py (levels 0 to 4 or unset, decisions/incident-management.md vocabulary): stored records depend on it, so it stays code. Which of those levels a declare or update offers is organisation policy (teams use different scales until the organisation standardises), so it becomes a typed setting per decisions/configuration.md (plain constants are avoided). Raised 2026-11-27 by the human at the TASK-145.7.10 cutover, where the pickers were made to derive from Severity (SEVERITY_OPTIONS in features/incident/response/entrypoints/slack_show_views.py). Single PR from main after 18.L9b merges.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 [incident_core] offered_severities, an ordered list of levels with a base.toml default of [0, 1, 2, 3, 4]; boot fails naming the key on an empty list, a duplicate or a value outside Severity
- [ ] #2 The Slack declare form and the update modal offer unset plus exactly the configured levels in order, read at call time; a stored severity outside the configured list still shows in show and preselects nothing in the update modal
- [ ] #3 decisions/incident-management.md vocabulary names the setting: the closed set is the domain's, the offered subset is configuration; every channel (Slack, a future Teams adapter, the HTTP API input check) derives from them
- [ ] #4 ruff, mypy (no new errors in touched files), make check-settings-key-ownership, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
