---
id: TASK-25
title: >-
  Apply the outbound-client contract: clients raise, adapters classify; retire
  the executor/shield tier
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-22
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/operation-result.md
  - 'https://github.com/cds-snc/sre-bot/issues/1279'
priority: high
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md. One adaptation tier: integrations/<vendor>/ provides (1) authenticated client factories with SDK-native retry/timeouts configured once and (2) classify_<vendor>_error(exc) -> (OperationStatus, error_code, retry_after). Clients raise typed SDK exceptions - they never return OperationResult. The Protocol implementation (Path A composed service or Path B feature adapter) is the single boundary: try/except around the client call, classify, return OperationResult.

Steps:
1. Per vendor (aws, google_workspace, maxmind, slack): write classify_<vendor>_error mapping EXPECTED SDK exception families to status/error_code/retry_after. Unexpected exceptions (KeyError etc.) are NOT classified - they propagate.
2. Refactor AWSShield (app/integrations/aws/shield.py) into factory config + classification function; delete the standing wrapper class and the executor middle tier. Blocking SDK calls invoked from async code get asyncio.to_thread offload.
3. Update adapters/composed services to the try/except-classify pattern; remove pass-through secondary adaptation.
4. grep-verify: no time.sleep/tenacity/backoff retry loops in app/integrations/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each vendor package exports exactly: factories, classify_<vendor>_error, settings
- [ ] #2 No client returns OperationResult; adapters/composed services produce it via the classification function (spot-check per vendor + import-linter contract from task-18)
- [ ] #3 Classification tests per vendor: each mapped exception family -> expected status/error_code/retry_after; one unmapped exception propagates
- [ ] #4 AWSShield class deleted; grep -rn "shield" app/integrations returns zero code hits
- [ ] #5 grep: no hand-rolled retry (time.sleep/tenacity/backoff) in app/integrations/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All tests pass; import-linter contracts still green
- [ ] #2 PR references decisions/outbound-clients.md
<!-- DOD:END -->
