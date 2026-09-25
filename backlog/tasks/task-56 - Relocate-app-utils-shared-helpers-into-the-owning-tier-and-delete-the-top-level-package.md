---
id: TASK-56
title: >-
  Relocate app/utils/ shared helpers into the owning tier and delete the
  top-level package
status: To Do
assignee: []
created_date: '2026-07-27 16:08'
updated_date: '2026-09-24 20:07'
labels:
  - architecture
  - layers
  - migration
milestone: m-5
dependencies: []
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1360'
  - decisions/plugin-architecture.md
priority: medium
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24: decisions/layers.md is deleted. decisions/migration.md's non-layer directory table now owns this directory's disposition. Each symbol moves to its owning feature or capability, or to app/contracts/ when it crosses layers, without adding a forbidden import (decisions/plugin-architecture.md). A symbol used only by a legacy surface moves with that surface's rebuild rather than ahead of it.

app/utils/ is a top-level directory outside the three-tier model (decisions/migration.md) holding grab-bag shared helpers (utils/filters.py plus utils/models.py, utils/tests.py). filters is the live one: it is imported by CURRENT-tier code, not just legacy modules - app/integrations/aws/identity_store.py and app/integrations/google_workspace/google_directory.py both do from utils import filters, alongside app/modules/* consumers.

A shared top-level utils/ bag is exactly the ambiguous, ownerless location the layering model exists to eliminate; helpers belong with the tier that owns them (integrations-level data-shaping helpers stay near their integrations, or become a small typed helper module in the consuming tier), not in a cross-cutting top-level package that every layer reaches into.

Scope: enumerate utils/* symbols and consumers, assign each a proper owner honoring the downward-only import rule (a shared helper used by integrations must not force an upward import), repoint imports, and delete app/utils/. Assess whether utils/models.py / utils/tests.py are dead and can be removed outright.

Needs a human-approved implementation plan (task-planner) before any code; the plan must confirm no relocation introduces an upward/sideways import that violates decisions/migration.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every symbol in app/utils/ has an assigned owner (feature, capability, contracts/ if it crosses layers, or its legacy surface's rebuild ticket), documented in the plan, with no forbidden import across the layer boundary
- [ ] #2 All import sites of utils.* are repointed
- [ ] #3 Dead members of app/utils/ (e.g. models.py, tests.py if unused) are identified and removed rather than relocated
- [ ] #4 app/utils/ no longer exists; utils is removed from the import-linter root packages and the decisions/migration.md table row is removed; existing tests pass under new import paths
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 15:27
---
2026-09-14 (TASK-25.2.3 series): the description and AC#2 name app/integrations/aws/identity_store.py as a current-tier consumer of utils.filters. That module was deleted by TASK-25.2.3.2.4, and packages/aws_platform/adapters/identity_center.py does not import utils. Current production utils.* import sites (rg, excluding tests): modules/provisioning/groups.py:7, modules/provisioning/users.py:10, modules/provisioning/entities.py:4 and modules/aws/identity_center.py:9 (utils.filters); modules/slack/webhooks.py:17 and modules/webhooks/base.py:17 (utils.models). Tests importing utils: tests/utils/test_filters.py, tests/api/routes/test_system.py, tests/api/v1/test_webhooks.py, tests/api/v1/test_geolocate.py, tests/integration/api/v1/test_geolocate_routes.py. google_directory.py should be re-checked when this task is planned. Human: consider rewording AC#2 so it no longer names the deleted file (not changed here).
---
<!-- COMMENTS:END -->
