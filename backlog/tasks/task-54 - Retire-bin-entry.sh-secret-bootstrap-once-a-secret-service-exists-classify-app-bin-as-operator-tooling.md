---
id: TASK-54
title: >-
  Retire bin/entry.sh secret bootstrap once a secret service exists; classify
  app/bin/ as operator tooling
status: To Do
assignee: []
created_date: 2026-07-27 16:07
updated_date: '2026-10-23T17:08:00Z'
labels:
  - architecture
  - layers
  - configuration
milestone: m-4
dependencies: []
references:
  - decisions/configuration.md
  - decisions/security.md
  - https://github.com/cds-snc/sre-bot/issues/1358
  - decisions/migration.md
priority: medium
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/bin/ is operator and dev tooling (entry.sh container entrypoint, db.sh, seed.sh, dev-token.py, unlock-sync-job.sh, generate_client_usage_matrix.sh and the CI check scripts), not app runtime code and exempt from the layer contracts; decisions/migration.md's directory table records this. entry.sh is the container entrypoint (Dockerfile:77) and still writes the sre-bot-config and sre-bot-config-infrastructure SSM parameters to .env at start. decisions/configuration.md (Secrets): secrets reach the app as SSM SecureString parameters through task-definition secrets: and no container-start script fetches configuration, so no secret service is built. TASK-111.15.1 removes entry.sh's SSM fetch; TASK-111.15.2 checks AC #3 once that deploy is verified. decisions/migration.md's bin/ row still ties the retirement to a secrets contract implementation and is brought in line.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/migration.md's directory table classifies app/bin/ as operator and dev tooling, exempt from the layer contracts
- [ ] #2 decisions/migration.md's bin/ row states that entry.sh fetches no configuration and secrets come through task-definition secrets: (decisions/configuration.md), not a secrets contract implementation
- [ ] #3 app/bin/entry.sh fetches no SSM parameter and only starts the app, verified against the running task definition (TASK-111.15.1)
- [ ] #4 No secret- or configuration-fetching logic exists in app/bin/
<!-- AC:END -->
