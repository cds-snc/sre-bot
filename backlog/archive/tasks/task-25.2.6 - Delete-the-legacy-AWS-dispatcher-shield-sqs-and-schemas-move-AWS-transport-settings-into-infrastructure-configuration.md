---
id: TASK-25.2.6
title: >-
  Delete the legacy AWS dispatcher, shield, sqs, schemas and the infrastructure
  AWS settings module; prune the guard baselines
status: Done
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-24 20:35'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.3
  - TASK-25.2.4
  - TASK-25.2.5
references:
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - app/integrations/aws/shield.py
  - app/integrations/aws/sqs.py
  - app/integrations/aws/schemas.py
  - app/infrastructure/configuration/integrations/aws.py
  - app/infrastructure/configuration/integrations/__init__.py
  - app/packages/access/sync/adapters/aws_identity_center.py
  - app/bin/check_vendor_package_contract.py
  - app/bin/check_sdk_typing.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (final) of TASK-25.2. With no mirror module left, remove from integrations/aws/client.py: handle_aws_api_errors, execute_aws_api_call, paginator, assume_role_session, get_aws_service_client and the module-level constants re-exported from settings (SYSTEM_ADMIN_PERMISSIONS, VIEW_ONLY_PERMISSIONS, AWS_REGION, THROTTLING_ERRS, RESOURCE_NOT_FOUND_ERRS). Delete integrations/aws/shield.py (this executes TASK-25.5: zero production consumers), sqs.py (zero consumers) and schemas.py (unused Pydantic models). integrations/aws/settings.py STAYS: it is the colocated home of all AWS settings until TASK-88 (human decision 2026-09-11); shield.py's AWSSettings usage is simply removed with shield.

Retire infrastructure/configuration/integrations/aws.py and its AwsSettings/get_aws_settings export from infrastructure/configuration/integrations/__init__.py (that barrel is why AWS settings were moved out of infrastructure/configuration). Its last reader is packages/access/sync/adapters/aws_identity_center.py (SERVICE_ROLE_MAP and INSTANCE_ID); since TASK-25.2.2 gives integrations/aws/settings.py the same field names, repoint that single import line and nothing else in packages/access. Small direct edits to packages/access for this repoint are fine; the access feature is not enabled yet, so anything beyond keeping it importing and passing its tests is out of scope.

Tests deleted: tests/unit/integrations/aws/{test_executor,test_shield}.py, tests/integrations/aws/{test_sqs,test_legacy_aws_client}.py, tests/smoke/integrations/aws/test_shield_smoke.py; the AWS entries in tests/unit/infrastructure/configuration/test_integration_settings_singletons.py go with the infrastructure module; tests/unit/integrations/aws/conftest.py keeps its AWSSettings fixture for client.py tests.

Guardrails: bin/baselines/vendor_package_contract.txt and bin/baselines/sdk_typing_antipatterns.txt end with no integrations/aws entries; make check-vendor-package-contract, make check-sdk-typing and make client-usage-matrix are run and their output recorded. decisions/outbound-clients.md gets at most one short dated sentence if the eager AssumeRole choice needs recording.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/aws/ contains only __init__.py, client.py and settings.py; client.py exports get_aws_client and classify_aws_error only
- [x] #2 shield.py, sqs.py, schemas.py and the listed tests are deleted; grep -rn shield app/integrations returns zero code hits
- [x] #3 infrastructure/configuration/integrations/aws.py and its barrel export are deleted, with packages/access repointed to integrations/aws/settings.py
- [x] #4 Both guard baselines have no integrations/aws entries and the three make checks pass with output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR (decomposed 2026-09-18; see the comment above for full rationale and grep evidence). This task's own direct implementation work is retired in favor of three dependency-chained subtasks, each individually planned and sized under the single-PR gate:

1. TASK-25.2.6.1 — delete integrations/aws/sqs.py and schemas.py (zero production consumers) and their orphaned test.
2. TASK-25.2.6.2 (depends on .1) — delete client.py's legacy dispatcher tier and shield.py; empty the sdk_typing_antipatterns baseline; close decisions/sdk-typing.md's four tolerated anti-patterns.
3. TASK-25.2.6.3 (depends on .2) — delete infrastructure/configuration/integrations/aws.py and its barrel export; repoint packages/access; close decisions/outbound-clients.md's shield tolerance.

This task's four ACs map onto the subtasks as: AC#1+AC#2 -> .1 and .2 together (integrations/aws/ ends as __init__.py+client.py+settings.py, shield grep-clean); AC#3 -> .3; AC#4 -> .1+.2 for the baselines, .2+.3 for the two ADR edits and the standard gates. Do not check any of this task's ACs directly — check them off only once every subtask that contributes to that AC is Done and verified, per each subtask's own AC traceability. Work each subtask through its own branch/PR in dependency order; do not batch them into one PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Coordinator closed by its subtasks TASK-25.2.6.1, TASK-25.2.6.2 and TASK-25.2.6.3 (all Done; TASK-25.2.6.3 landed in #1501). Verified on 2026-09-24 against the working tree:
- AC1: app/integrations/aws/ holds only __init__.py, client.py and settings.py. The only public functions in client.py are get_aws_client (Literal overloads) and classify_aws_error; the rest are private helpers.
- AC2: shield.py, sqs.py and schemas.py are gone; rg -i shield app/integrations returns no hits.
- AC3: infrastructure/configuration/integrations/aws.py is gone, with no importer; packages/access/sync/adapters/aws_identity_center.py imports integrations.aws.settings.get_aws_settings.
- AC4: neither app/bin/baselines file has an integrations/aws entry. make check-sdk-typing reported "OK: no net-new SDK anti-patterns (0 baselined file(s) remain)". make check-vendor-package-contract reported "OK: no net-new vendor-package contract violations (16 baselined entry(ies) remain)", none of them AWS. make check-aws-platform-seam reported "OK: no net-new packages.aws_platform consumers (11 baselined consumer(s) remain)"; that seam is owned by TASK-88.
Left for the human: move to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 15:36
---
2026-09-18 DECOMPOSED per the single-PR size gate. A combined single-PR estimate came to ~639 production LOC across 11 production files (client.py edit, shield.py/sqs.py/schemas.py/infrastructure aws.py deletes, the infra barrel edit, the packages/access repoint, two baseline edits, two ADR edits) — over both the ~400 LOC and ~10 file thresholds, so it must not be handed off as one plan. Repo-wide grep (2026-09-18) confirmed the task's prose was still accurate: shield.py/sqs.py/schemas.py have zero production consumers, the infra aws.py module has exactly one remaining reader (packages/access/sync/adapters/aws_identity_center.py) with confirmed field-name parity to integrations/aws/settings.py, and the Google-side sdk-typing anti-patterns (execute_google_api_call, get_google_api_command_parameters, google_service.py, *_next.py) and the AWSClients facade are already fully gone repo-wide.

Split into three dependency-ordered subtasks, each independently shippable/revertible and under the size gate:
- TASK-25.2.6.1: delete integrations/aws/sqs.py + schemas.py (zero consumers) and their test file; prune the vendor_package_contract baseline's schemas/sqs lines. ~2 production files.
- TASK-25.2.6.2 (deps: .1): delete client.py's legacy dispatcher tier (lines 224-432: handle_aws_api_errors, assume_role_session, get_aws_service_client, execute_aws_api_call, paginator, the five re-exported constants) and shield.py; empty the sdk_typing_antipatterns baseline and prune shield's vendor_package_contract lines; close all four of decisions/sdk-typing.md's tolerated anti-patterns in its Migration section (with a dated Changes line, not a status/applies flip). ~4 production files.
- TASK-25.2.6.3 (deps: .2, since client.py's own import of the legacy infra module must be gone first): delete infrastructure/configuration/integrations/aws.py and its barrel export; repoint packages/access/sync/adapters/aws_identity_center.py's single import; remove decisions/outbound-clients.md's closed 'shield-shaped AWS client' tolerance bullet with a dated Changes line. ~4 production files.

Each subtask's --plan carries full grep-grounded steps, AC traceability, a test matrix, assumptions/doubts and blast-radius/rollback notes. This task (TASK-25.2.6) is now a coordinator: its four ACs are satisfied once all three subtasks are Done — do not re-check them here directly, and do not move this task's own status past To Do (an agent stops at In Progress with notes; only a human moves a task to Done, and that applies to the coordinator once its children close).

Two deliberate scope boundaries carried into the subtasks, flagged for human awareness rather than decided here: (1) decisions/sdk-typing.md's `applies: target` frontmatter is NOT flipped to `now` even though its Checks appear to all pass after TASK-25.2.6.2 — that's a broader claim (e.g. re-verifying MaxMind/Slack have no vendor-facade class) than this task's grep scope covers. (2) bin/check_sdk_typing.py's own "Retirement" docstring says to delete the script once its baseline is empty (which it will be after .2) — not done here, left for a human to decide since the task's AC only asks for an empty baseline and passing checks, not script retirement.
---
<!-- COMMENTS:END -->
