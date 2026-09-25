---
id: TASK-32
title: Delete the README-only app/infrastructure/notifications/ placeholder
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:04'
labels:
  - infrastructure
  - phase-4
  - plugin-architecture
milestone: m-7
dependencies: []
references:
  - 'https://github.com/cds-snc/sre-bot/issues/1286'
  - decisions/plugin-architecture.md
priority: low
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24. app/infrastructure/persistence/ no longer exists (verified 2026-09-24). app/infrastructure/notifications/ holds only a README saying "to be rebuilt".

decisions/plugin-architecture.md lists notifications among the shared business capabilities, so its home is app/capabilities/notifications/, not infrastructure/, and it is built with its first consumer (the "no approvers found" operator alert rehomed by TASK-61). A placeholder in infrastructure/ points contributors at the wrong layer. Delete it.

The former second AC (a note on which infrastructure services are deliberately Protocol-less) is obsolete. Framework services move to app/server/ with their contracts in app/contracts/ (TASK-107, TASK-115, TASK-116, TASK-118), and the reference to the deleted decisions/layers.md no longer applies.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/notifications/ does not exist, and no empty or README-only package exists under app/infrastructure/
- [ ] #2 No doc or task points contributors at infrastructure/ for notifications; decisions/ and README references name app/capabilities/notifications/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR merged with maintainer sign-off on the delete-vs-build choice
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 13:20
---
Scope note from a 2026-07-28 architecture review: if notifications/ is REBUILT (rather than deleted), it must be a capability-shaped NotificationService Protocol with Email/SMS channels, vendor specifics (GC Notify, SNS, SES) in adapters per outbound-clients.md. Critically: durable 'must be delivered even if we crash' delivery is QueueService work (TASK-34), NOT a bespoke queue inside notifications/ - the channel adapter is only the sender. This makes notifications a concrete driver/consumer for TASK-34. The persistence/ half is unaffected (storage/ covers it - default remains delete).
---

created: 2026-09-10 15:45
---
ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Do not introduce new infrastructure services for workplace concerns: calendar, documents, files, directory, mail, notifications, people or identity. That means no new app/infrastructure/<service>/ package, Protocol or factory.

Why: the organization will run Google Workspace with Slack and Microsoft 365 with Teams side by side for the long term. Three Draft decision records describe the direction:
- decisions/workplace-systems.md
- decisions/capability-packages.md
- decisions/people-and-accounts.md

Until those are accepted:
- keep vendor behavior in feature Path B adapters (app/packages/<feature>/adapters/);
- the existing infrastructure/directory, drive and spreadsheets providers stay usable, including changes needed to finish migrating their current consumers;
- do not create capability packages yet.

Resolve app/infrastructure/notifications/ by deleting it, not by building it. Reaching a person on Slack or Teams is a workplace concern (decisions/workplace-systems.md, Draft). Do not build app/infrastructure/persistence/ as a new service either: durable storage is StorageService's job (TASK-27).
---
<!-- COMMENTS:END -->
