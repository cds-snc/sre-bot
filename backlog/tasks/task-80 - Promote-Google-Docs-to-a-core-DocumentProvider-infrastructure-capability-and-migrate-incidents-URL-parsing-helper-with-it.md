---
id: TASK-80
title: >-
  Promote Google Docs to a core DocumentProvider infrastructure capability and
  migrate incident's URL-parsing helper with it
status: To Do
assignee: []
created_date: '2026-09-08 18:27'
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
