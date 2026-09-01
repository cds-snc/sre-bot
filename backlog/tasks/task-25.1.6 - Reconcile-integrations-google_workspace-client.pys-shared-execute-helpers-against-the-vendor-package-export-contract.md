---
id: TASK-25.1.6
title: >-
  Reconcile integrations/google_workspace/client.py's shared execute helpers
  against the vendor-package export contract
status: To Do
assignee: []
created_date: '2026-09-01 15:31'
updated_date: '2026-09-01 17:30'
labels:
  - clients
  - phase-3
  - cleanup
dependencies:
  - TASK-25.1.1
  - TASK-25.1.2
  - TASK-25.1.3
  - TASK-25.1.4
  - TASK-25.1.5
references:
  - decisions/outbound-clients.md
  - app/integrations/google_workspace/client.py
  - app/integrations/google_workspace/google_docs.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1
priority: medium
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md's Checks require each vendor package to export exactly: factories, classify_<vendor>_error, settings — "the adapter is the boundary", not the vendor client. TASK-22.4 already added one narrow deviation (execute_batch_request, needed only for the Directory batch API's per-item error-reporting shape). TASK-25.1.1 added a second, more general one: execute_google_api_request(request), a shared try/except+classify_google_error+log+raise helper in integrations/google_workspace/client.py, reused by TASK-25.1.1/.2/.3/.5's call sites.

CORRECTION (2026-09-01): this task's original framing — "decide between (a) inline per-adapter or (b) keep execute_google_api_request as a permanent, formalized shared primitive" — was inaccurate and is replaced. decisions/outbound-clients.md already decided the target shape (one adaptation tier: clients raise, adapters classify). execute_google_api_request performing classification inside the vendor package is a real, currently-necessary deviation from that decision, not a genuinely open two-way choice. It is tolerated only because today's actual Google Workspace call sites have no compliant adapter tier to inline the try/except into: TASK-25.1.1/.2's consumers are legacy app/modules/incident/*.py files with zero error handling of their own, plus app/packages/incident_draft/adapters/google_docs.py — a real packages/<feature>/adapters/ file (per decisions/feature-packages.md) that itself performs no try/except/classify today either.

Reconciliation must correct this deviation, not ratify it as permanent. Once all of TASK-25.1's children (Calendar/Meet, Docs, Sheets, legacy Directory consumers, Drive) are Done and the full execute_google_api_request call-site inventory is known, this task's job is to: (1) inline try/except + classify_google_error directly at every call site that already lives in a real packages/<feature>/adapters/ or infrastructure/ file, deleting that call site's dependency on execute_google_api_request; (2) for every remaining call site that is legacy app/modules/* code with no adapter tier, file (or point at) the follow-up work that migrates it onto a real per-feature adapter — this may itself need its own decomposition, since building a first adapter for app/modules/incident's Google Docs/Drive/Calendar usage is new architecture, not a mechanical inline; (3) delete execute_google_api_request from client.py entirely once no call site depends on it. Keeping it as a permanent vendor-package export is not an acceptable resolution of this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The full execute_google_api_request call-site inventory across TASK-25.1.1/.2/.3/.4/.5 is enumerated, naming which call sites already live in a real packages/<feature>/adapters/ or infrastructure/ file vs. which are legacy app/modules/* code with no adapter tier
- [ ] #2 Every call site already in a real packages/<feature>/adapters/ or infrastructure/ file has its own inline try/except + classify_google_error + raise, and no longer depends on execute_google_api_request
- [ ] #3 Every remaining legacy app/modules/* call site either has its own real per-feature adapter built and inlined, or a follow-up task migrating it there is filed/linked here; execute_google_api_request is deleted from client.py once zero call sites depend on it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CALL-SITE INVENTORY — TASK-25.1.2 (Docs) contribution, recorded 2026-09-01 at implementation time:

app/integrations/google_workspace/google_docs.py now has 3 execute_google_api_request call sites (all added by TASK-25.1.2, none pre-existing):
- create() -> service.documents().create(body=...)
- batch_update() -> service.documents().batchUpdate(documentId=..., body=...)
- get_document() -> service.documents().get(documentId=...)

AC#1 classification for these 3: NONE live in a real packages/<feature>/adapters/ or infrastructure/ file. google_docs.py is the vendor module itself, and its downstream production consumers are:
- app/modules/incident/incident_document.py, incident_status.py, incident_conversation.py, information_update.py — legacy app/modules/* with no adapter tier and no try/except around any google_docs call (AC#3 bucket).
- app/packages/incident_draft/adapters/google_docs.py — real adapters/ file, already named in comment #2 above (AC#2 bucket); it calls google_docs.get_document/batch_update rather than execute_google_api_request directly, so reconciling it means pointing it at get_docs_service + its own inline try/except, which then removes 2 of the 3 sites' reason to exist for that path.

So after TASK-25.1.2 the helper's known call sites are: TASK-25.1.1's (Calendar/Meet) + these 3 (Docs). Siblings .3/.4/.5 still to report.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-01 16:54
---
Corrected 2026-09-01 (task-planner, while planning TASK-25.1.2): the original 'inline vs. formalize-as-permanent' framing implied this was a fair two-option architectural choice. It is not — decisions/outbound-clients.md already decided the target (clients raise, adapters classify, one tier). execute_google_api_request is a tolerated, temporary deviation, not a candidate to become permanent. Description and ACs rewritten accordingly (bulk --acceptance-criteria replace). The real blocker to full reconciliation is that today's Google Workspace call sites (app/modules/incident/*.py, and app/packages/incident_draft/adapters/google_docs.py which is a real adapters/ file but performs no try/except/classify of its own) mostly have no compliant adapter to inline into — that gap may need its own follow-up task(s) once the full call-site inventory is known, not a unilateral 'keep the helper' decision.
---

created: 2026-09-01 17:13
---
Concrete instance for AC#2/#3 (2026-09-01, human-confirmed while planning TASK-25.1.2): app/packages/incident_draft/adapters/google_docs.py is a real packages/<feature>/adapters/ file (post-dates the original TASK-25.1 consumer inventory) that today calls google_docs.get_document/batch_update (the legacy module-level passthrough) with ZERO try/except of its own — target shape is to call integrations.google_workspace.client.get_docs_service directly and do its own inline try/except+classify_google_error. Deliberately deferred out of TASK-25.1.2 (not an oversight): its test file is 1704 lines with 44 patch(...) sites keyed to the current google_docs mock boundary, and building real classify-based error handling here is new business logic (OperationStatus-to-None/[]-on-failure mapping for read_sections/write_draft_document), not a mechanical rewire — combining it with 25.1.2's own work would exceed a reviewable single PR. When this task is picked up, treat this adapter as a named, already-identified item in the call-site inventory, not something to re-discover.
---
<!-- COMMENTS:END -->
