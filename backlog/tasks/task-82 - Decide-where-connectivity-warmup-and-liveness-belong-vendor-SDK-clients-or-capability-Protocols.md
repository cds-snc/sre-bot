---
id: TASK-82
title: >-
  Decide where connectivity warmup and liveness belong: vendor SDK clients or
  capability Protocols
status: To Do
assignee: []
created_date: '2026-09-09 15:26'
labels:
  - architecture
  - clients
dependencies: []
references:
  - decisions/dependency-injection.md
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/health-checks.md
  - app/infrastructure/directory/provider.py
  - app/infrastructure/drive/provider.py
  - app/server/lifespan.py
priority: medium
ordinal: 164000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ANALYSIS + DECISION-RECORD TASK, raised 2026-09-09 by the human while reviewing TASK-25.1.6.10.2's plan. No accepted decision record says a capability Protocol should carry warmup() or health_check() methods, yet two of them do, and copying that shape into every new capability is becoming a reflex.

EVIDENCE GATHERED WHILE PLANNING TASK-25.1.6.10.2 (grep-verified 2026-09-09):
- DirectoryProvider and DriveProvider both declare warmup() and health_check().
- DirectoryProvider.warmup() has real callers: server/lifespan.py:172 (gated on DirectorySettings.require_startup_warmup, raising RuntimeError on failure) and modules/dev/google.py:55 (a diagnostic Slack command).
- DriveProvider.warmup() has ZERO production callers. DriveProvider.health_check() has ZERO production callers. DirectoryProvider.health_check() has ZERO production callers. The only production health_check() call in the app is on the i18n translation service (server/lifespan.py:220), which is not a vendor-backed capability at all.
- So of four declared methods across the two vendor capabilities, one is used and three are ceremony that every new capability is expected to reproduce.
- GoogleDriveProvider.health_check() returns OperationResult.success unconditionally without touching the service - a method that cannot fail is not a liveness check.
- The Sheets capability (TASK-25.1.6.10.2) exposed the shape as impractical rather than merely unused: the Sheets API has no listing or about endpoint reachable without a spreadsheet id, so there is no cheap connectivity probe to implement. Both methods were dropped from SpreadsheetProvider on that basis (human-directed).

WHAT THE RECORDS ACTUALLY SAY:
- decisions/dependency-injection.md's 'eager composition at startup' is about lifespan phase 2 INVOKING EVERY REGISTERED PROVIDER so construction and validation happen at boot. That is provider construction, not a warmup() method on each capability contract. The registry it describes does not exist yet ('no warmup registry exists yet').
- decisions/health-checks.md is entirely about container/ECS/ALB/Route53 HTTP checks. It says nothing about provider Protocols.
- decisions/outbound-clients.md puts authenticated client construction in integrations/<vendor>/. Credential validity and reachability are properties of that construction, which is the human's instinct here: the thing worth warming up is the configured vendor SDK client, not each capability service layered above it.

QUESTION TO DECIDE: should connectivity warmup and liveness be (a) a per-capability Protocol method as today, (b) a concern of the vendor client factory in integrations/<vendor>/ invoked once at startup per configured vendor, (c) part of the dependency-injection provider registry's eager phase-2 invocation with no capability-level method at all, or (d) a mix keyed on whether a cheap probe endpoint exists for that vendor surface. Whatever is chosen, record it - the current situation is an unrecorded convention that new capabilities copy without a reason.

OUTPUT: an amendment to decisions/dependency-injection.md (or a new record) stating where warmup/liveness lives, plus follow-up tasks to reconcile DirectoryProvider, DriveProvider and any capability built in the meantime.

NOT IN SCOPE OF THIS TASK: implementing the change. Decide and record first; reconciliation is separate work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A written decision states where connectivity warmup and liveness belong (vendor client factory, DI provider registry, capability Protocol, or a keyed mix) with the alternatives and tradeoffs recorded
- [ ] #2 The decision is captured as an amendment to an existing decision record or a new one, and its Checks section is mechanically verifiable
- [ ] #3 The unused DriveProvider.warmup/health_check, DirectoryProvider.health_check and the unconditionally-successful GoogleDriveProvider.health_check are explicitly addressed by the decision (kept with a stated purpose, or scheduled for removal via follow-up tasks)
- [ ] #4 The decision states what a capability should do when its vendor surface offers no cheap probe endpoint, using Google Sheets as the worked example
- [ ] #5 Follow-up reconciliation tasks are created; no production code is changed by this task
<!-- AC:END -->
