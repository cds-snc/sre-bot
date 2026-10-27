---
id: TASK-126
title: >-
  Credential checks: a plugin declares read-only checks the host runs after
  registration; a failure alerts and never aborts boot
status: To Do
assignee: []
created_date: 2026-09-25 14:58
updated_date: '2026-10-27T18:11:00Z'
labels:
  - plugin-architecture
  - plugins
  - observability
milestone: m-7
dependencies:
  - TASK-98
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/lifecycle.md
  - https://github.com/cds-snc/sre-bot/issues/1672
priority: medium
ordinal: 274000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/lifecycle.md and plugins.md: a fault in state that changes without a deploy (an IAM role or permission removed, a secret rotated, a vendor down) never aborts boot. Aborting on it would turn a one-plugin fault into a whole-app outage at the next task restart or scale-out, and a rollback cannot fix it. terraform/ecs.tf runs desired_count = 2 with the circuit breaker's rollback on, so a deploy whose new tasks abort keeps serving from the old ones; a restart after IAM drift has no old task to fall back on. Configuration defects are not this task: they abort boot (TASK-172).

SCOPE:
- A register_credential_checks hookspec in contracts/ lets a feature or capability that depends on a credential declare checks; plugins that don't implement it make no network call at boot.
- Each check is a cheap read-only call on the API it uses, through its adapter, one attempt, bounded timeout, returning OperationResult. The host runs the declared checks concurrently after registration.
- UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed; TRANSIENT_ERROR logs WARNING credential_check_inconclusive. Neither aborts boot or unregisters the plugin; it keeps serving and returns the failing status until the credential is fixed, then recovers without a restart.
- access/sync's interim check from TASK-98 moves onto the hookspec, and a startup_warmup no longer makes the network call that aborts boot on a credential failure. The feature-package generator (TASK-114) and decisions/feature-packages.md mention the hookspec.

The existing error and warning alarms report these events (decisions/observability.md; TASK-94 moves them to JSON fields).

Motivating case: someone removes the IAM role access sync assumes. The app, including incident handling, keeps serving through any restart, while the error alarm reports access sync as broken.

Standalone PR: it changes boot semantics (backlog doc-2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A contracts/ hookspec lets a plugin declare a credential check; the host runs the checks concurrently after registration with a bounded deadline
- [ ] #2 UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed and TRANSIENT_ERROR logs WARNING credential_check_inconclusive; boot completes and the plugin stays registered in both cases (boot tests)
- [ ] #3 access/sync's check uses the hookspec and no startup_warmup makes a network call that aborts boot on a credential failure; under a socket.connect spy, startup opens outbound connections only from declared checks (boot test)
- [ ] #4 decisions/lifecycle.md and plugins.md Migration drop the raising-startup_warmup credential tolerance
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
