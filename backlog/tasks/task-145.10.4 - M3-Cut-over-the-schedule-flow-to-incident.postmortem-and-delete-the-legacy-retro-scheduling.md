---
id: TASK-145.10.4
title: >-
  M3 Cut over the schedule flow to incident.postmortem and delete the legacy
  retro scheduling
status: To Do
assignee: []
created_date: '2026-11-20T22:04:00Z'
updated_date: '2026-11-20T22:05:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.10.3
parent_task_id: TASK-145.10
priority: medium
ordinal: 535000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M3, the production-changing cutover. plugin.py, entrypoints/slack.py, entry point incident.postmortem (features.incident.postmortem.plugin) and contract (m), requirements (slack.tenant, google_workspace.tenant, incident_postmortem.calendar_id), enablement keys (ci off), ids under incident.postmortem.*, the nudge button claimed through the value-scoped alias (archive_channel scoped to schedule_retro). Deletes modules/incident/schedule_retro.py, its three registrations, the incident_helper schedule branch and the archive_channel_action schedule_retro branch. Named changes NC1-NC10 listed in the PR body with kinds (NC9 = availability model, kind (b); pins test_incident_retro_schedule_surface.py:159 and :175 edited citing the ruling). Waits on PR #1867 merged (i18n rule). Human before merge: INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production; no Sentinel query reads the schedule-button event. ADR: incident-management.md Postmortem availability paragraph. Branch stack-m/145.10.4-cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 incident.postmortem registers the schedule command, modal and nudge button; the legacy schedule_retro.py, registrations and branches are deleted
- [ ] #2 Pins pass with assertions unchanged except the named changes cited in the PR body (NC1-NC10 with kind and revert target)
- [ ] #3 calendar_id required at registration; ci and base enablement keys set; boot test keeps entry points equal to contract (m)
- [ ] #4 incident-management.md Postmortem availability paragraph written; INVENTORY.md rows updated
- [ ] #5 ruff, mypy, the four make checks and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded outline (plan in full at pickup; waits on PR #1867 merged). Depends on M2b.
Grounding: response precedents plugin.py, entrypoints/slack.py, slack_archive.py (register_attachment_action with legacy_callback_values={archive_channel: (archive,)}), scope.py; legacy removal anchors: schedule_retro.py (385 lines), incident_helper.py :23, :136-138, :155, :247-264, incident_conversation.py :20, :393-399, :417-421, tests/unit/server/test_server_app_import_google_settings_lazy.py:26; pyproject entry points :44-46 and contract (m) :439-453; config/base.toml [plugins.incident_response] :282-285, config/ci.toml :11-16 (requirement guard); host_configuration.py :22,:247.
Steps: plugin.py (register_requirements: slack.tenant, google_workspace.tenant, incident_postmortem.calendar_id; commands; i18n resource), entrypoints/slack.py (command /sre incident schedule [retro], picker actions, confirm button, submission, button press via value-scoped alias on id incident.postmortem.schedule; vocabulary constant), pyproject + enablement, delete legacy, rewire pins (add plugin to SLACK_COMMAND_HOOKIMPLS, conftest.py:98), INVENTORY.md rows 60-63, ADR Postmortem availability paragraph. Named changes NC1-NC10 in the PR body with kind and revert target: NC1 refused insert shows a failure view (a); NC2 not-an-incident by record, private localized (b); NC3 meeting reference stored (b); NC4 EN/FR text (b); NC5 Sentinel minimal payload (b); NC6 member without email skipped (a); NC7 DST/holidays (a); NC8 description, reminder, requestId sent (a, TASK-86); NC9 availability model (b; pins test_incident_retro_schedule_surface.py:159 and :175 edited citing the ruling); NC10 guests cannot modify or invite (b). Pin NC1 is renamed test_legacy_only_* in a first commit. Human before merge: INCIDENT_POSTMORTEM__CALENDAR_ID non-empty in production; no Sentinel query reads the schedule-button event. Blast radius: the only production change of the first four layers; one git revert restores legacy.
<!-- SECTION:PLAN:END -->
