---
id: TASK-145.7.10
title: >-
  Cut over /incident, the declare modal, locale toggle, alert buttons and SEV0;
  delete the legacy declare
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-17T19:10:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.7.8
  - TASK-145.7.9
references:
  - decisions/incident-management.md
  - decisions/transport-slack.md
  - decisions/webhooks.md
  - decisions/reliability.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 514000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L9b, size exception approved 2026-11-09 (approved program in TASK-145.7's plan, section 2; outline in the parent plan). Registers /incident, view incident.response.declare (validates before its single ack), action incident.response.locale, and the alert buttons incident.response.alert_buttons with handle_incident_action_buttons as a legacy alias (the producer keeps posting the legacy id until L9c); ignore claims the action (reliability.md:18) and increments through the interim AlertAcknowledgements adapter (approximate count, webhooks.md line); SEV0 in the declare and update pickers. Deletes the legacy declare, incident_alert handler, registrations and app/models/incidents.py; rewires the declare pins; deletes legacy_acknowledged_webhooks_seam and baseline lines 9 and 17. One revert restores the legacy declare.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The declare and alert-button pins pass with assertions unchanged except the deliberate SEV0 option; legacy registrations are gone (checks parent ACs #1, #4, #6, #11)
- [ ] #2 legacy_acknowledged_webhooks_seam and baseline lines 9 and 17 are deleted; app/models/incidents.py is gone (Incident and IncidentPayload) with the L5r rollback guard: features/incident/core/adapters/legacy_rollback.py and every TODO(TASK-145.7.10) site, and their tests tests/unit/models/test_models_incident_legacy_attribute_load.py, tests/factories/legacy_rollback.py, tests/unit/features/incident/core/test_incident_core_legacy_rollback_{view,write,round_trip}.py and tests/unit/modules/incident/test_incident_db_operations_update_field_marker.py; rg finds no importer of models.incidents or legacy_rollback, including tests/modules/incident and tests/integration/legacy_surface
- [ ] #3 decisions/webhooks.md records acknowledged_count as approximate and the interim adapter as tolerated
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #5 The declare pin names the deliberate list-sheet changes: the extra column F (incident id), the status value TASK-145.7.9 picked if it differs from In Progress, and an empty product column until TASK-165.1 maps product names; the PR body states them for the sheet's readers (TASK-145.12.1 rulings, 2026-11-16)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7 rulings R4-R6): the cut-over Slack declare follows the record-first order (create, then the conversation and attach_conversation, then resources); the legacy pins that assert channel-before-record ordering are updated deliberately in this task's plan.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---

created: 2026-11-17T19:10:00Z

---

2026-11-17 (found at the Stack L sync, TASK-145.8.5.3 session): #1853 (fba4ff8b, merged to main, not a Stack L change) added a policy-help answer to the legacy declare: production-only invite of the policy group ([incident] policy_group_id in features/incident/response/settings.py; modules/incident/core.py and incident.py; pinned in tests/modules/incident/test_incident_core.py and test_incident.py, 15 policy tests). The declare rebuild carries it (pins rewired, not dropped) or rules it a named change at planning.

---
<!-- COMMENTS:END -->
