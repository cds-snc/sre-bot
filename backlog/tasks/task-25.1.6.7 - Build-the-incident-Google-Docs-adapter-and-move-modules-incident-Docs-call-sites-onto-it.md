---
id: TASK-25.1.6.7
title: >-
  Build the incident Google Docs adapter and move modules incident Docs call
  sites onto it
status: To Do
assignee: []
created_date: '2026-09-02 15:02'
updated_date: '2026-09-03 15:10'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-25.1.6.6
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - decisions/layers.md
  - app/integrations/google_workspace/google_docs.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 138000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First of the legacy-incident adapter slices, and the one that makes the architectural choice the rest inherit.

CONSUMERS (grep-confirmed): app/modules/incident/incident_document.py, incident_status.py, incident_conversation.py, information_update.py all call integrations.google_workspace.google_docs.create / batch_update / get_document directly. None has a try/except of its own; all rely on the vendor package's execute_google_api_request. These are legacy app/modules/* files with NO adapter tier, which is precisely why TASK-25.1.1 through .5 could not inline classification and had to leave the deviation in place.

THE DECISION THIS SLICE MUST MAKE FIRST, because .8 (Drive), .9 (Calendar/Meet) and .10 (Sheets) all follow it: where does the incident feature's Google boundary live? The options are (a) a real app/packages/incident/adapters/ file, which means starting the incident feature package - a strangler move with scope well beyond Docs; (b) an adapter module inside app/modules/incident/ that satisfies the boundary contract (own factory call, own try/except + classify, own typed results) without yet claiming to be a package; (c) reuse or extend an existing package adapter. decisions/copilot-instructions treats app/modules as legacy and not an architectural reference, and decisions/feature-packages.md governs (a). Pick one, write the rationale into the notes, and state it in the PR - do not leave the next three slices to re-litigate it.

SCOPE ONCE DECIDED: the chosen adapter builds a stub-typed DocsResource from integrations.google_workspace.client.get_docs_service, calls documents().create / .batchUpdate / .get directly, does its own try/except + classify_google_error, translates responses into typed results (decisions/sdk-typing.md item 3), and the four modules/incident files call the adapter instead of the vendor module. integrations/google_workspace/google_docs.py is then deleted (TASK-25.1.6.6 removes its only other consumer) along with extract_google_doc_id's relocation from TASK-25.1.6.2.

DO NOT reproduce the vendor module's create/batch_update/get_document signatures in the adapter. They are SDK mirrors; the adapter's methods should express what the incident feature actually needs (create an incident document, replace a section, read the current body), not what the Docs API endpoints are named. Reproducing the mirror one layer up would defeat the entire exercise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The architectural decision for where the incident feature's Google boundary lives is made, written into the task notes with its rationale, and stated in the PR description; TASK-25.1.6.8/.9/.10 reference it rather than re-deciding
- [ ] #2 The chosen adapter builds a stub-typed DocsResource via get_docs_service, calls documents().create/.batchUpdate/.get directly, and performs its own try/except + classify_google_error
- [ ] #3 The adapter's public methods are expressed in incident-domain terms and return typed results, not SDK-shaped passthroughs mirroring create/batch_update/get_document
- [ ] #4 All four consumers (incident_document.py, incident_status.py, incident_conversation.py, information_update.py) call the adapter; none imports integrations.google_workspace
- [ ] #5 app/integrations/google_workspace/google_docs.py is deleted with its test file, grep-verified zero references repo-wide outside backlog/ and tmp/
- [ ] #6 Existing incident tests pass, with any intentional behaviour change (in particular what each consumer now does on a classified Docs failure, which today is an unhandled propagation) named explicitly in the notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 14:21
---
SCOPE NARROWING from TASK-25.1.6.2 planning (2026-09-03, task-planner). TASK-25.1.6.2's plan removes the `from integrations.google_workspace import google_docs` import from incident_conversation.py, incident_status.py and information_update.py entirely — grep-confirmed each file's ONLY use of google_docs was extract_google_doc_id (now relocated to modules/incident/utils.py), none of the three calls create/batch_update/get_document. So once TASK-25.1.6.2 lands, this task's AC#4 ("none imports integrations.google_workspace") is already true for 3 of the 4 named consumers before this task starts — only incident_document.py will still import google_docs (for batch_update/get_document), and it is therefore the only file this task's adapter migration needs to repoint for the "none imports" half of AC#4. The adapter itself, its try/except+classify_google_error, and the create/batchUpdate/get typed-result work are unaffected and still needed exactly as scoped.
---

created: 2026-09-03 15:10
---
CORRECTION to the 2026-09-03 comment above (task-planner). That comment claimed TASK-25.1.6.2 would remove the google_docs import from incident_conversation.py, incident_status.py and information_update.py entirely. That is no longer accurate: TASK-25.1.6.2 was re-scoped mid-planning to defer extract_google_doc_id's relocation to THIS task, specifically because this task is the one deciding where the incident feature's Google-boundary package lives, and creating a second, unrelated new package name for extract_google_doc_id in TASK-25.1.6.2 risked colliding with that undecided shape. TASK-25.1.6.2 now only relocates the 4 Calendar-availability helpers (to a new app/packages/incident_scheduling/ package, per decisions/migration.md's new rule 5). extract_google_doc_id stays in app/integrations/google_workspace/google_docs.py untouched, and all 4 named consumers (incident_document.py, incident_status.py, incident_conversation.py, information_update.py) still import google_docs exactly as today. This task's own scope (AC#4/#5) is unchanged by TASK-25.1.6.2 after all — disregard the narrowing claimed in the prior comment.
---

created: 2026-09-03 15:10
---
ACTIONABLE FOR THIS TASK: extract_google_doc_id itself is not a Google SDK call (pure regex over a URL string) - it does not belong in whatever adapter this task builds for create/batchUpdate/get. When this task deletes google_docs.py, it must also decide extract_google_doc_id's destination. It qualifies for decisions/migration.md's new rule 5 lighter path (no hookimpl/entry-point needed) the same way TASK-25.1.6.2's app/packages/incident_scheduling/ does - likely its own small package or a domain.py inside whichever package this task creates for the incident Docs boundary.
---
<!-- COMMENTS:END -->
