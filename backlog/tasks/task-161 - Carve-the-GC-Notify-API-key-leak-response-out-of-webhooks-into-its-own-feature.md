---
id: TASK-161
title: Carve the GC Notify API-key leak response out of webhooks into its own feature
status: To Do
assignee: []
created_date: '2026-10-22T19:05:00Z'
updated_date: '2026-10-23T18:09:00Z'
labels:
  - webhooks
  - configuration
dependencies: []
references:
  - https://github.com/cds-snc/sre-bot/issues/1782
priority: low
ordinal: 432000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The AWS SNS pattern modules/webhooks/patterns/aws_sns_notification/api_key_detected.py is an organization-specific feature hidden inside the webhooks module: when a GC Notify API key is reported as leaked, it revokes the key through the Notify client and alerts Notify ops (channel and on-call group). Carve it into its own feature package under features/, receiving the payload through the webhooks capability's extension point (decisions/webhooks.md, decisions/plugin-architecture.md), with its settings class moved from modules/webhooks/patterns/aws_sns_notification/settings.py into the feature; the [notify_api_key_leak] table created by TASK-111.7 stays as it is (decisions/configuration.md: table names do not depend on module paths). Not queued: it follows the incident (TASK-145) and SRE feature refactors and is planned with the webhooks rearchitecture (TASK-37), whose current scope does not cover it. Notify's own 'skip the revoke outside production' ENVIRONMENT check (integrations/notify/client.py) becomes a configuration value of this feature here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The API-key leak response is a feature package registered through the webhooks capability's extension point; modules/webhooks no longer contains it
- [ ] #2 Its settings class lives in the feature and still reads [notify_api_key_leak]; no ENVIRONMENT check decides where it posts or whether it revokes
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
