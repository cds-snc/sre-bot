---
id: TASK-101
title: >-
  Close the orphan-lease window when the SDK exhausts retries after the claim
  landed
status: To Do
assignee: []
created_date: '2026-09-17 20:39'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies:
  - TASK-25.2.5.4
references:
  - app/infrastructure/idempotency/dynamodb.py
  - app/integrations/aws/settings.py
  - app/bin/unlock-sync-job.sh
priority: medium
ordinal: 229000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while planning TASK-25.2.5.4 on 2026-09-17; human decision the same day to keep it out of that PR because it changes claim()'s error contract, which no acceptance criterion there covers.

THE WINDOW. TASK-25.2.5.4 gives claim() a per-call claim token that rescues the SDK replay which REACHES ConditionalCheckFailedException. A second exit is not covered. AWS_RETRY_MAX_ATTEMPTS defaults to 3, i.e. four attempts total (app/integrations/aws/settings.py:42-46). If attempt 1's conditional PutItem lands but its response is lost, and the remaining attempts also fail on a timeout or 5xx rather than reaching the condition, botocore raises a transient error. claim() then hits app/infrastructure/idempotency/dynamodb.py:76-79, classify_aws_error returns TRANSIENT_ERROR with a code that is not ConditionalCheckFailedException, and claim() raises RuntimeError. Meanwhile our record holds the lease. Nobody runs until IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS expires - the same orphan-lease outcome the claim token was added to prevent, through a different exit.

The window is much narrower than the replay it complements: all four attempts must fail after one of them landed. It is not zero, and it is exactly the scenario a retry budget exists to produce.

CANDIDATE FIX (for the planner to confirm, not a mandate). On a classified non-conditional failure, re-read before raising and return NEW if the item carries this call's claim token. That reuses the token TASK-25.2.5.4 already writes and needs no Protocol change, but it turns a raise into a return for one error class, so the callers of claim() - and the error mapping documented for them - have to be checked. app/bin/unlock-sync-job.sh is the existing operator escape hatch for a lease already stuck this way and should be mentioned in whatever is decided, not silently replaced.

Interaction with TASK-100 (fail-open flip): if that lands first, this path may fold into the same policy decision rather than needing its own branch. Sequence them deliberately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A claim whose conditional put landed but whose SDK attempts were exhausted by transient failures does not leave a lease held with no runner
- [ ] #2 claim()'s error contract after the change is stated explicitly, and every production caller is checked against it
- [ ] #3 An unclassified error still propagates unchanged, and a genuine transient failure with no landed write still surfaces as a failure rather than a false NEW
<!-- AC:END -->
