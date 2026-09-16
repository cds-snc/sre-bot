---
id: TASK-80
title: >-
  SUPERSEDED: Promote Google Docs to a core DocumentProvider infrastructure
  capability
status: To Do
assignee: []
created_date: '2026-09-08 18:27'
updated_date: '2026-09-16 14:37'
labels: []
dependencies: []
references:
  - app/packages/incident/documents/adapters/google_docs.py
  - app/packages/incident/documents/utils.py
  - TASK-25.1.6.7
priority: low
ordinal: 154000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SUPERSEDED AND ARCHIVED 2026-09-16. Not aligned with the current direction; do not act on this task.

decisions/workplace-systems.md (2026-09-10) postdates this task and answers its question with no. Rule 1 bars a new app/infrastructure/<service>/ Protocol for documents, files, calendar, mail and similar workplace concerns: a neutral contract across whole suites is the lowest-common-denominator trap, and routing by person or artifact is organization policy that infrastructure must not hold. The infrastructure/directory/ DirectoryProvider precedent this task was built on is itself named in that record as sitting in the wrong tier, alongside infrastructure/drive/ and infrastructure/spreadsheets/.

REPLACEMENT EXPECTATION, so the original intent is not lost: if document I/O is ever needed by more than one feature, it becomes a capability package with one adapter per workplace system (decisions/capability-packages.md), never a vendor-neutral infrastructure Protocol. packages/incident/documents/utils.py::extract_google_doc_id stays feature-local until such a package exists, and TASK-38 AC#10 keeps it and every other vendor-shaped helper behind a feature-owned adapter boundary. Whether the incident feature keeps a document concept at all is an open question owned by TASK-97.

ORIGINAL DESCRIPTION, kept for the record:
Forward-looking architectural note raised in review of TASK-25.1.6.7 (which shipped app/packages/incident/documents/adapters/google_docs.py, a plain-function Google Docs adapter with no Protocol, and app/packages/incident/documents/utils.py holding extract_google_doc_id, a pure Google-Docs-URL-ID parser with zero SDK I/O). extract_google_doc_id is feature-local today only because it is the sole Google-Docs-URL helper that exists. Per decisions/layers.md, a portable-capability Protocol belongs in infrastructure/, not packages/<feature>/adapters/ - mirroring the infrastructure/directory/ DirectoryProvider precedent (TASK-22.4), which promoted a Google Directory capability out of a feature-local adapter into a vendor-neutral infrastructure Protocol. If Google's 'document' concept is ever promoted the same way (a DocumentService/DocumentProvider Protocol in app/infrastructure/), extract_google_doc_id should migrate alongside it rather than staying stranded in packages/incident/documents/. This task exists so that expectation is not lost, not to schedule the work now.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
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

THIS TASK'S PREMISE CONFLICTS WITH THE CONSTRAINT. A core infrastructure DocumentProvider must not be built:
- AC#1's decision is effectively made: no infrastructure DocumentProvider. If a second feature needs document operations, that becomes a capability package once decisions/capability-packages.md is accepted.
- AC#2 does not apply: extract_google_doc_id stays feature-local.
- Incident and talent-role records are moving into storage, so documents become collaboration spaces or projections (decisions/workplace-systems.md).

The acceptance criteria are left unchanged. A human should re-scope or close this task.
---

author: @claude
created: 2026-09-16 14:25
---
2026-09-16: this task predates decisions/workplace-systems.md (2026-09-10), which answers its AC#1 with no. Rule 1 bars a new app/infrastructure/<service>/ Protocol for documents, files, calendar, mail and similar workplace concerns, on the lowest-common-denominator argument and because routing by person or artifact is organization policy that infrastructure must not hold; the DirectoryProvider precedent this task cites is itself named in that record as sitting in the wrong tier. If document I/O turns out to be needed by more than one feature, the replacement expectation is a capability package with one adapter per system (decisions/capability-packages.md), not a vendor-neutral infrastructure Protocol. extract_google_doc_id stays feature-local until such a capability package exists. Re-scoping or closing this task is an explicit acceptance criterion of TASK-97.
---
<!-- COMMENTS:END -->
