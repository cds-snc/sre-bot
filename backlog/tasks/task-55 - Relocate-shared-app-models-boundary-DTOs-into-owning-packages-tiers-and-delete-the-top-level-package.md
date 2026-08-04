---
id: TASK-55
title: >-
  Relocate shared app/models/ boundary DTOs into owning packages/tiers and
  delete the top-level package
status: To Do
assignee: []
created_date: '2026-07-27 16:07'
updated_date: '2026-07-27 16:13'
labels:
  - architecture
  - layers
  - migration
milestone: m-5
dependencies: []
references:
  - decisions/layers.md
  - decisions/migration.md
  - decisions/operation-result.md
  - 'https://github.com/cds-snc/sre-bot/issues/1359'
priority: medium
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/models/ is a top-level directory outside the three-tier model (decisions/layers.md) holding shared Pydantic boundary DTOs: models/webhooks.py (WebhookPayload, AwsSnsPayload, WebhookResult), models/incidents.py (Incident, IncidentPayload). These are I/O-boundary models per decisions/operation-result.md and the model-boundary rules, but a single shared top-level bag is not a sanctioned home.

Important: unlike locales/ (deleted wholesale at strangler completion, TASK-41), app/models/ has live consumers OUTSIDE app/modules/ - app/api/v1/routes/webhooks.py imports models.webhooks - so it cannot simply vanish when modules/ is deleted; each DTO must be repointed to its owning feature package (webhooks/incident, per decisions/migration.md ordering) or the tier that owns the boundary, then the top-level package removed.

Scope of this task: enumerate every models/* symbol and its consumers, assign each a target owner (feature package boundary module), repoint imports, and delete app/models/. Coordinated with the webhooks (TASK-37) and incident (TASK-38) migrations that own most consumers.

Needs a human-approved implementation plan (task-planner) before any code; may need decomposition per the single-PR size gate if the webhooks and incident DTO moves cannot land in one reviewable PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every symbol in app/models/ (webhooks.py, incidents.py) has an assigned target owner (a feature package boundary module or the owning tier), documented in the plan
- [ ] #2 All import sites of models.* - including non-module consumers app/api/v1/routes/webhooks.py, app/integrations/* - are repointed to the new locations
- [ ] #3 app/models/ no longer exists as a top-level package; layers.md non-tier-directories section records this ticket as its disposition
- [ ] #4 Existing tests for the moved DTOs pass under their new import paths
<!-- AC:END -->
