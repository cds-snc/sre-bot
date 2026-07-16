---
id: TASK-22
title: >-
  Migrate the seven baselined consumers off infrastructure/clients/ and delete
  the deprecated trees
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-19
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - 'https://github.com/cds-snc/sre-bot/issues/1276'
priority: high
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/layers.md (Migration) and decisions/outbound-clients.md. Today three client generations coexist: empty app/clients/ (aborted name), deprecated app/infrastructure/clients/{aws,google_workspace,maxmind}/ (72 files) still imported at runtime by the baselined consumers (infrastructure/storage/service.py:19, infrastructure/directory/factory.py:6, infrastructure/directory/google.py:7, packages/geolocate/service.py, packages/access/sync/providers.py, packages/access/sync/adapters/aws_identity_center.py), and current app/integrations/.

Steps:
1. Run make client-usage-matrix (task-19) to get the authoritative consumer list (the plan counted 7 baselined files).
2. Migrate each consumer to the app/integrations/ equivalent, one consumer (or one vendor) per PR to keep review small.
3. After the last consumer: delete app/infrastructure/clients/ entirely and the empty app/clients/ directory.
4. Empty the corresponding baseline in app/bin/baselines/ as consumers migrate (the freeze check enforces monotonic shrinkage).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 make client-usage-matrix reports zero consumers of infrastructure/clients/
- [ ] #2 app/infrastructure/clients/ and app/clients/ no longer exist; decisions/layers.md check "no directory named clients/ under app/" passes
- [ ] #3 Deprecated-import baseline file is empty
- [ ] #4 All tests pass after each per-consumer PR, not just the last one
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: no functional change per migrated consumer (existing tests unchanged except import paths)
- [ ] #2 PR series references decisions/layers.md
<!-- DOD:END -->
