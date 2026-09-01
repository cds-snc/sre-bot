---
id: TASK-25.1.6
title: >-
  Reconcile integrations/google_workspace/client.py's shared execute helpers
  against the vendor-package export contract
status: To Do
assignee: []
created_date: '2026-09-01 15:31'
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
parent_task_id: TASK-25.1
priority: medium
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md's Checks require each vendor package to export exactly: factories, classify_<vendor>_error, settings. TASK-22.4 already added one deviation (execute_batch_request, needed for the Directory batch API). TASK-25.1.1 is planned to add a second, more general one (execute_google_api_request(request), a shared try/except+classify_google_error+log+raise helper reused across get_freebusy/insert_event/create_space, intended for reuse by TASK-25.1.2/.3/.5 too) as a deliberate, temporary, documented deviation -- not a silent violation. This task exists so that deviation does not become permanent by default.

Once all of TASK-25.1's children (Calendar/Meet, Docs, Sheets, legacy Directory consumers, Drive) are Done and every call site's actual shape through execute_google_api_request is known, decide and execute ONE of:
(a) Inline classify_google_error + logging directly into each adapter call site (per-call try/except, per outbound-clients.md's literal 'adapter is the boundary' wording) and delete execute_google_api_request entirely from client.py, accepting the repetition outbound-clients.md's cost tradeoff already names ('adapter authors write the try/except themselves... that is the price of not maintaining a wrapper layer'); or
(b) Keep execute_google_api_request as a permanent, intentional shared primitive and update decisions/outbound-clients.md's Checks/Consequences to explicitly allow a thin shared execute-and-classify helper per vendor package (mirroring how sdk-typing.md was itself revised in place when new facts emerged), documenting why a 4th export is justified for this vendor (repeated Resource.execute() + classify + log + raise shape across many discovery-API call sites, unlike single-call-site vendors).

Do not let this decision default silently either way; it must be made explicitly with the full call-site inventory in hand, and decisions/outbound-clients.md updated if option (b) is chosen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision (inline-per-adapter vs. formalize-as-shared-primitive) is made and recorded, citing the full call-site inventory across all TASK-25.1 children
- [ ] #2 If inlined: execute_google_api_request no longer exists in integrations/google_workspace/client.py and every former call site has its own try/except + classify_google_error + raise
- [ ] #3 If formalized: decisions/outbound-clients.md's Checks/Consequences are updated to explicitly permit a shared execute-and-classify helper per vendor package, with rationale
<!-- AC:END -->
