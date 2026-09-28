---
id: TASK-128
title: >-
  Replace the boot-time directory warmup with a classified credential check;
  delete DIRECTORY_REQUIRE_STARTUP_WARMUP /
  DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS
status: To Do
assignee: []
created_date: '2026-09-25 14:58'
updated_date: '2026-09-25 15:54'
labels:
  - lifecycle
  - clients
milestone: m-4
dependencies:
  - TASK-92
references:
  - app/server/lifespan.py
  - app/infrastructure/directory/settings.py
  - decisions/lifecycle.md
priority: medium
ordinal: 276000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/server/lifespan.py:166-177 still calls directory_provider.warmup() when DIRECTORY_REQUIRE_STARTUP_WARMUP is true. The call makes two Google connections (admin.googleapis.com, oauth2.googleapis.com, measured 2026-09-17) and raises RuntimeError on failure, so a Google Workspace outage or a bad credential stops every task start. The opt-in defaults to false. Whether production sets it is recorded in the SSM parameters (TASK-111 inventory).

decisions/lifecycle.md allows exactly one kind of boot-time network call: a classified credential check that alerts on failure and never aborts boot. The directory warmup is opt-in, raises on any failure (a Google outage included) and is not classified.

Scope: replace the lifespan directory warmup with a classified credential check that always runs when the directory is in use: one cheap read-only Directory call, one attempt, bounded timeout. UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed; TRANSIENT_ERROR logs WARNING credential_check_inconclusive. Neither aborts boot (decisions/lifecycle.md). Delete both settings (app/infrastructure/directory/settings.py) with their tests. Before deleting, check the SSM inventory, and if production sets either variable, remove it from the parameter in the same change. DirectoryProvider.warmup() itself stays: modules/dev/google.py:55 calls it from a diagnostic Slack command, and TASK-127 decides the fate of the provider probe methods.

Standalone PR: it changes boot behaviour (backlog doc-2). Where production had the opt-in on, a bad Google credential no longer fails boot; everywhere, it now raises an ERROR alert at boot.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DIRECTORY_REQUIRE_STARTUP_WARMUP and DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS no longer exist in code, tests, terraform or docs (rg), and the production SSM parameter no longer sets them (recorded in notes)
- [ ] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #3 decisions/lifecycle.md Migration drops the directory warmup from its tolerated network I/O
- [ ] #4 Lifespan runs the directory credential check: an UNAUTHORIZED result logs ERROR credential_check_failed and a TRANSIENT_ERROR result logs WARNING credential_check_inconclusive; boot completes in both cases (lifespan tests with a fake directory)
<!-- AC:END -->
