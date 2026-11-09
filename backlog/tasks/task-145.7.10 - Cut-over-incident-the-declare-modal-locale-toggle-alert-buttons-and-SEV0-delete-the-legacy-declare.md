---
id: TASK-145.7.10
title: >-
  Cut over /incident, the declare modal, locale toggle, alert buttons and SEV0;
  delete the legacy declare
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
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
- [ ] #2 legacy_acknowledged_webhooks_seam and baseline lines 9 and 17 are deleted; app/models/incidents.py is gone
- [ ] #3 decisions/webhooks.md records acknowledged_count as approximate and the interim adapter as tolerated
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
