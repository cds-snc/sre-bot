---
id: TASK-25.1.6.11
title: >-
  Delete execute_google_api_request and enforce the Google Workspace vendor
  export contract
status: To Do
assignee: []
created_date: '2026-09-02 15:04'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.5
  - TASK-25.1.6.8
  - TASK-25.1.6.9
  - TASK-25.1.6.10
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 142000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Closing slice of TASK-25.1.6. Small by design: every consumer has already moved, so this is deletion plus a guardrail.

BY THIS POINT the six vendor mirror modules are gone (google_directory.py via TASK-25.1.6.5; google_docs.py via .7; google_drive.py via .8; google_calendar.py and meet.py via .9; sheets.py via .10) and every Google call site lives in an adapter that does its own try/except + classify_google_error. The temporary shared helper therefore has zero callers.

SCOPE:
1. Delete integrations/google_workspace/client.py::execute_google_api_request and its tests. It was introduced by TASK-25.1.1 as an explicitly temporary, in-code-documented deviation from decisions/outbound-clients.md's export contract, because no compliant adapter existed to inline it into. That reason is gone.
2. Decide execute_batch_request's fate. TASK-22.4 added it as a narrower deviation, needed for the Admin SDK batch protocol's per-item error-reporting shape, and it returns OperationResult from inside the vendor package - which decisions/outbound-clients.md forbids ("no client returns OperationResult", TASK-25 AC#2). Its only consumer is GoogleDirectoryProvider. Either move the batch orchestration into that provider (leaving the vendor package with factories + classify only) or record why the batch protocol genuinely cannot be expressed at the adapter, as an explicit amendment to decisions/outbound-clients.md rather than a silent exception.
3. Verify and lock in the export contract: app/integrations/google_workspace/ contains client.py (factories + classify_google_error) and settings, and nothing else.
4. Add the guardrail so this cannot regress: extend app/bin/check_sdk_typing.py (or the equivalent CI check) to fail when app/integrations/<vendor>/ gains a module that is neither a factory/classification/settings module, or when a file under app/integrations/ imports OperationResult outside the classification return type. A convention this expensive to re-establish should be machine-enforced, not remembered.

THEN: TASK-25.1's AC#1 and TASK-25's AC#1/#2 become provable for the Google vendor, and TASK-25.1.6 can close.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/client.py::execute_google_api_request is deleted with its tests; grep confirms zero references repo-wide outside backlog/ and tmp/
- [ ] #2 execute_batch_request is either moved into infrastructure/directory/google.py (vendor package left with factories + classify only) or retained with a written amendment to decisions/outbound-clients.md explaining why the batch protocol cannot be expressed at the adapter - not left as a silent exception
- [ ] #3 app/integrations/google_workspace/ contains only client.py and settings; the six mirror modules (google_calendar, meet, google_docs, sheets, google_drive, google_directory) and google_service.py are all gone
- [ ] #4 No file under app/integrations/ returns OperationResult except as part of a classify_<vendor>_error return type (TASK-25 AC#2, spot-checked and covered by the guardrail below)
- [ ] #5 A CI guardrail fails the build when app/integrations/<vendor>/ gains a non-factory/non-classification/non-settings module, and it is proven by a deliberately failing fixture in the check's own tests
- [ ] #6 app/bin/baselines/sdk_typing_antipatterns.txt has zero remaining google_workspace entries and python3 bin/check_sdk_typing.py passes
<!-- AC:END -->
