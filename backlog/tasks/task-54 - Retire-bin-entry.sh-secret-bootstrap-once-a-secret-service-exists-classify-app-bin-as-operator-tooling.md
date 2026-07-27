---
id: TASK-54
title: >-
  Retire bin/entry.sh secret bootstrap once a secret service exists; classify
  app/bin/ as operator tooling
status: To Do
assignee: []
created_date: '2026-07-27 16:07'
updated_date: '2026-07-27 16:13'
labels:
  - architecture
  - layers
  - configuration
milestone: m-4
dependencies: []
references:
  - decisions/layers.md
  - decisions/configuration.md
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1358'
priority: medium
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/layers.md does not account for app/bin/, a top-level directory of operator and dev shell/python tooling (entry.sh container entrypoint, db.sh, seed.sh, dev-token.py, unlock-sync-job.sh, generate_client_usage_matrix.sh). It is not application code and does not belong to any tier, but it is currently load-bearing: the container image runs bin/entry.sh as its entrypoint, which fetches configuration/secrets at boot.

Two things this task settles:
1. Record app/bin/ as sanctioned operator/dev tooling (not app runtime code, exempt from the three-tier import rule) in the layers.md non-tier-directories section, so it is not mistaken for a stray package to delete.
2. entry.sh's boot-time secret/config fetching must be retired once a dedicated secret service capability is introduced (a larger change per decisions/configuration.md and decisions/security.md). This task is the acknowledged tracking item for that deprecation: when the secret service lands, entry.sh stops sourcing secrets itself and the entrypoint is simplified or removed.

Depends on the secret service capability existing; until then this is the placeholder that keeps the coupling visible. Needs a human-approved implementation plan (task-planner) before any code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 layers.md non-tier-directories section classifies app/bin/ as operator/dev tooling exempt from the tier import rule (not a stray package slated for deletion)
- [ ] #2 The dependency of bin/entry.sh on boot-time secret/config fetching is documented as the trigger to retire it once a secret service capability exists
- [ ] #3 Once the secret service is available, entry.sh no longer sources secrets itself and the container entrypoint is simplified or removed, with the change verified against the deployment manifest
- [ ] #4 No new secret-fetching logic is added to app/bin/ after the secret service exists
<!-- AC:END -->
