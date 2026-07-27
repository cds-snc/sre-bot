---
id: TASK-56
title: >-
  Relocate app/utils/ shared helpers into the owning tier and delete the
  top-level package
status: To Do
assignee: []
created_date: '2026-07-27 16:08'
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
  - 'https://github.com/cds-snc/sre-bot/issues/1360'
priority: medium
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/utils/ is a top-level directory outside the three-tier model (decisions/layers.md) holding grab-bag shared helpers (utils/filters.py plus utils/models.py, utils/tests.py). filters is the live one: it is imported by CURRENT-tier code, not just legacy modules - app/integrations/aws/identity_store.py and app/integrations/google_workspace/google_directory.py both do from utils import filters, alongside app/modules/* consumers.

A shared top-level utils/ bag is exactly the ambiguous, ownerless location the layering model exists to eliminate; helpers belong with the tier that owns them (integrations-level data-shaping helpers stay near their integrations, or become a small typed helper module in the consuming tier), not in a cross-cutting top-level package that every layer reaches into.

Scope: enumerate utils/* symbols and consumers, assign each a proper owner honoring the downward-only import rule (a shared helper used by integrations must not force an upward import), repoint imports, and delete app/utils/. Assess whether utils/models.py / utils/tests.py are dead and can be removed outright.

Needs a human-approved implementation plan (task-planner) before any code; the plan must confirm no relocation introduces an upward/sideways import that violates decisions/layers.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every symbol in app/utils/ has an assigned owner in a sanctioned tier location, documented in the plan, with no resulting upward/sideways import across the layer boundary
- [ ] #2 All import sites of utils.* - including current-tier consumers app/integrations/aws/identity_store.py and app/integrations/google_workspace/google_directory.py - are repointed
- [ ] #3 Dead members of app/utils/ (e.g. models.py, tests.py if unused) are identified and removed rather than relocated
- [ ] #4 app/utils/ no longer exists as a top-level package; layers.md non-tier-directories section records this ticket as its disposition; existing tests pass under new import paths
<!-- AC:END -->
