---
id: TASK-80
title: >-
  Promote Google Docs to a core DocumentProvider infrastructure capability and
  migrate incident's URL-parsing helper with it
status: To Do
assignee: []
created_date: '2026-09-08 18:27'
updated_date: '2026-09-10 15:45'
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
Forward-looking architectural note raised in review of TASK-25.1.6.7 (which shipped app/packages/incident/documents/adapters/google_docs.py, a plain-function Google Docs adapter with no Protocol, and app/packages/incident/documents/utils.py holding extract_google_doc_id, a pure Google-Docs-URL-ID parser with zero SDK I/O). extract_google_doc_id is feature-local today only because it is the sole Google-Docs-URL helper that exists. Per decisions/layers.md, a portable-capability Protocol belongs in infrastructure/, not packages/<feature>/adapters/ - mirroring the infrastructure/directory/ DirectoryProvider precedent (TASK-22.4), which promoted a Google Directory capability out of a feature-local adapter into a vendor-neutral infrastructure Protocol. If Google's 'document' concept is ever promoted the same way (a DocumentService/DocumentProvider Protocol in app/infrastructure/), extract_google_doc_id should migrate alongside it rather than staying stranded in packages/incident/documents/. This task exists so that expectation is not lost, not to schedule the work now.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision is made on whether Google Docs warrants a core infrastructure DocumentProvider Protocol (mirroring DirectoryProvider), based on evidence of multiple features needing document I/O beyond the incident feature
- [ ] #2 If promoted, packages/incident/documents/utils.py::extract_google_doc_id migrates alongside the new infrastructure capability instead of staying feature-local
<!-- AC:END -->

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
<!-- COMMENTS:END -->
