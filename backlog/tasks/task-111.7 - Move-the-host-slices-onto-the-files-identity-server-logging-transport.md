---
id: TASK-111.7
title: 'Move the host slices onto the files: identity, server, logging, transport'
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-21T20:23:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.5.2
  - TASK-111.16
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1754
parent_task_id: TASK-111
type: feature
ordinal: 413000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
AppSettings becomes the env-only identity slice (environment, git_sha) in server/configuration/; webhook_max_body_bytes moves to the server slice; server and the Slack transport read their non-secret values from the files (backend_url, notify ops/oncall ids, test channel, command_prefix); remaining secrets use <SLICE>__<FIELD>; extra=forbid; the dead ServerSettings fields and DevSettings are deleted; the import-time settings reads in server/server.py move into app creation. The logging slice is already on the files (TASK-111.2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The identity slice reads only ENVIRONMENT and GIT_SHA from the environment and no file
- [ ] #2 The server and transport slices read their non-secret production values from the files, set extra=forbid, and declare no per-field alias
- [ ] #3 The unused ServerSettings fields (google_client_id, google_client_secret, secret_key, access_token_expire_minutes, access_token_max_age_minutes) and DevSettings are deleted
- [ ] #4 server/server.py builds no settings at import time
- [ ] #5 .env.example, the pytest env and the CI workflow use the new names
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
