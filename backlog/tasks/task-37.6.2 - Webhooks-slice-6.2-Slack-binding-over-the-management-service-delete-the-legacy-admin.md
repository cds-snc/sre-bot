---
id: TASK-37.6.2
title: >-
  Webhooks slice 6.2: Slack binding over the management service; delete the
  legacy admin
status: To Do
assignee: []
created_date: '2026-11-25T20:49:00Z'
updated_date: '2026-11-27T16:47:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.5
  - TASK-37.6.1
  - TASK-36.1.4
references:
  - decisions/webhooks.md
  - decisions/transport-slack.md
  - decisions/migration.md
parent_task_id: TASK-37.6
priority: high
ordinal: 548000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Slack binding over the management service, and the deletion of the legacy admin (TASK-168 research packet section 5, row 37.6b, and Q10). A single PR from main.

Scope:
- /sre webhooks re-implemented over WebhookAdmin in the capability's entrypoints/slack.py, registered through the Slack handler contract; it requires webhooks:admin.
- Delete app/modules/slack/webhooks.py, webhooks_create.py, webhooks_list.py and app/modules/sre/webhook_helper.py; webhook_helper leaves the legacy registration list in server/lifespan.py; modules/slack/webhooks.py leaves the packages/aws_platform seam baseline, which unblocks TASK-88.
- The webhook URL shown to users is built from HostInfo.public_base_url ([server] public_base_url), not the host hard-coded in webhooks_create.py and webhooks_list.py (TASK-37 note of 2026-10-28).
- TASK-40 no longer rebuilds the webhook CRUD and admin views (OQ9).
- The TASK-36.1.4 admin pins hold, updated only where a named change applies (permission, owner field, reveal), each with its reason.

Out of scope: the API (TASK-37.6.1).

Size: ~250 production LOC.
Production: prod (Slack UI).
Revert / blast radius: one revert; the admin UI only.
Change notice: developer notice: management is in the API and Slack is one interface over it. User announcement with screenshots: /sre webhooks changes (permission, owner field, reveal) (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /sre webhooks is served by the capability's Slack binding over WebhookAdmin and requires webhooks:admin (test)
- [ ] #2 The TASK-36.1.4 admin pins pass, updated only where a named change applies (permission, owner field, reveal), each with its reason (test)
- [ ] #3 app/modules/slack/webhooks.py, webhooks_create.py, webhooks_list.py and app/modules/sre/webhook_helper.py are deleted; webhook_helper is absent from the legacy registration list in server/lifespan.py; modules/slack/webhooks.py leaves the packages/aws_platform seam baseline (grep)
- [ ] #4 The webhook URL shown to users is built from HostInfo.public_base_url, with no host written in code (test)
- [ ] #5 Deprecated-import and import-linter baselines shrank or held (check)
- [ ] #6 The PR body carries the developer change notice and the user announcement with screenshots (review)
- [ ] #7 The incident feature's interim AlertAcknowledgements adapter (marked TODO(TASK-37.6.2)) and its acknowledged_count increments are deleted; the attribute is no longer written, and stored items keep it untouched (test + grep)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 (Lane B, TASK-37.2.2 planning; Lane A hand-off from TASK-145.7.10): AC added. The adapter's TODO already names this task (migration.md rule 7) and webhooks.md lists it as tolerated until TASK-37.6.2, which replaces the legacy admin surface that displays the count.
<!-- SECTION:NOTES:END -->
