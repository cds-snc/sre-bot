---
id: TASK-37
title: Migrate modules/webhooks to a feature package
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-7
  - TASK-36
references:
  - decisions/migration.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1291'
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First strangler target per decisions/migration.md order (security-sensitive; 57 files - the largest module; gains signature auth from task-7). Includes the webhook_helper legacy-list entry. Follow the per-module recipe exactly; split the PR series by webhook provider if reviews get large.

Steps:
1. Verify task-36 smoke tests cover every webhook route this module exposes; add any missing before starting.
2. Build app/packages/webhooks/ per decisions/feature-packages.md layout: service.py orchestrates, store.py via StorageService, schemas.py at the trust boundary, interactions/http.py registers routes via hookspec, adapters/ for any vendor calls, locales/ if user-facing text exists.
3. Handlers follow the five-step discipline (receive -> translate -> one service call -> OperationResult -> render); webhook auth from task-7 applies at the route boundary.
4. Cut over: remove webhooks from _register_legacy_handlers() and any legacy route mounting; URLs unchanged; smoke tests green pre and post.
5. Delete app/modules/webhooks/ in the same PR series. No zombie halves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/webhooks/ matches the feature-packages layout table; import-linter green
- [ ] #2 Webhook URLs and behavior unchanged: task-36 smoke tests pass before and after cutover
- [ ] #3 app/modules/webhooks/ deleted; module absent from the legacy registration list
- [ ] #4 Deprecated-import and import-linter baselines shrank or held (never grew)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover; other-team-facing surface verified unchanged
- [ ] #2 PR series references decisions/migration.md recipe
<!-- DOD:END -->
