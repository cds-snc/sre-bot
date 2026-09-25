---
id: TASK-126
title: >-
  Feature isolation at boot: skip a feature with invalid settings, and a
  classified credential-check hookspec that alerts without aborting
status: To Do
assignee: []
created_date: '2026-09-25 14:58'
updated_date: '2026-09-25 16:02'
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
priority: medium
ordinal: 274000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/lifecycle.md and plugins.md (2026-09-25): only defects that ship with a deploy abort boot. State that changes without a deploy (an IAM role or permission removed, a secret rotated, a vendor down) never aborts boot. Aborting on it would turn a one-feature fault into a whole-app outage at the next task restart or scale-out, and a rollback cannot fix it. terraform/ecs.tf runs desired_count = 2 with the circuit breaker's rollback on and the default 100% minimum healthy, so a deploy whose new tasks abort keeps serving from the old ones. A restart after IAM drift has no old task to fall back on.

Fixed policy, no per-plugin override:
- An import error or a hookimpl raising during startup aborts boot in every layer (code defect, fixed by rollback).
- An invalid settings slice skips a feature: the host drops everything it registered before the registries freeze, unregisters it, and logs one CRITICAL plugin_boot_failed event (plugin, phase, error type, no secrets). An invalid capability or host slice aborts boot.
- CREDENTIAL CHECKS, OPT-IN PER PLUGIN. A register_credential_checks hookspec in contracts/ lets any feature or capability that depends on a credential declare checks; plugins that don't implement it make no network call at boot. Each check is a cheap read-only call on the API it uses, through its adapter, one attempt, bounded timeout, returning OperationResult. The host runs the declared checks concurrently after registration. UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed; TRANSIENT_ERROR logs WARNING credential_check_inconclusive. Neither aborts boot or unregisters the feature. It keeps serving and returns the failing status until the credential is fixed, then recovers without a restart. access/sync's interim check from TASK-98 moves onto the hookspec, and the feature-package generator (TASK-114) and decisions/feature-packages.md guidance mention the hook so new features know the option exists.

The existing error and warning alarms report these events (decisions/observability.md; TASK-94 moves them to JSON fields).

Motivating case: someone removes the IAM role access sync assumes. The app, including incident handling, must keep serving through any restart, while the error alarm reports access sync as broken.

Standalone PR: it changes boot semantics (backlog doc-2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Boot tests: an import error or a raising hookimpl aborts boot in every layer; a feature with an invalid settings slice is absent from every registry and from the OpenAPI schema while the other plugins serve; a capability with an invalid settings slice aborts boot
- [ ] #2 A skipped feature logs exactly one CRITICAL plugin_boot_failed event carrying plugin, phase and error type (test)
- [ ] #3 A contracts/ hookspec lets a plugin declare a credential check; the host runs the checks concurrently with a bounded deadline; UNAUTHORIZED/PERMANENT_ERROR/NOT_FOUND logs ERROR credential_check_failed and TRANSIENT_ERROR logs WARNING credential_check_inconclusive, boot completes and the feature stays registered in both cases (boot tests); access/sync's check uses the hookspec
- [ ] #4 decisions/lifecycle.md and plugins.md Migration drop the 'feature with invalid settings aborts boot' and raising-startup_warmup tolerances
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
