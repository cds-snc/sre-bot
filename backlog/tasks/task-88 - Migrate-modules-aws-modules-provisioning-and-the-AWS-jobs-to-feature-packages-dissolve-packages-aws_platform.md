---
id: TASK-88
title: >-
  Rebuild the modules/aws and modules/provisioning surfaces and the AWS jobs
  into app/features/; dissolve packages/aws_platform
status: To Do
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-24 20:09'
labels:
  - phase-5
dependencies:
  - TASK-25.2
  - TASK-36
  - TASK-38
  - TASK-109
  - TASK-114
references:
  - decisions/feature-packages.md
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
  - app/modules/aws
  - app/modules/provisioning
  - app/integrations/aws/settings.py
  - decisions/plugin-architecture.md
  - decisions/migration.md
priority: medium
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24 to decisions/plugin-architecture.md (which replaced the deleted capability-packages.md and layers.md) and migration.md:
- modules/aws and modules/provisioning are rebuilt by surface (TASK-36 inventory: target, smoke pin, rebuild, cutover), not migrated as modules.
- Each business feature lands in app/features/<feature>/ with its Path B adapters in its own adapters/.
- A shared Identity Center adapter goes to a capability in app/capabilities/ only when a second feature needs it (people-and-accounts, TASK-83, is the likely home).
- DynamoDB callers move onto the storage contract resolved from the service registry.
- No new app/infrastructure/<service>/ Protocol is created.
- packages/aws_platform can only be dissolved once incident persistence leaves the seam, which happens in the incident rebuild (TASK-38, after TASK-97).

Follow-up to TASK-25.2 (created 2026-09-11). modules/aws was named after a vendor but holds several business features with mixed concerns: AWS Ops group assignment (ops_group_assignment.py), AWS account health reporting (aws_account_health.py), spending reports (spending.py), Lambda inventory (lambdas.py), and Identity Center user/group administration (identity_center.py, users.py, groups.py, aws.py), which overlaps modules/provisioning/{users,groups}.py and the disabled packages/access feature. TASK-25.2 isolates their AWS SDK calls behind packages/aws_platform/adapters/, a provisional adapters-only package that is neither a feature nor a capability package.

Not in this inventory (human decision 2026-09-14): the AWS account access-request flow (aws_access_requests.py, the /aws access command, jobs/revoke_aws_sso_access.py). It was not operational in production and is deleted under TASK-25.2.3.2.4. packages/access re-provides that capability, so no feature package is built for it here.

This task decides the feature boundaries per decisions/feature-packages.md and decisions/plugin-architecture.md, migrates each module with the standard feature-package recipe (TASK-38 and TASK-39 are the incident and small-module precedents), moves each adapter into its owning home, types adapter returns as frozen domain dataclasses (decisions/sdk-typing.md item 3), relocates the feature-level AWS settings (permission sets, role ARNs, SSO instance, SERVICE_ROLE_MAP) out of integrations/aws/settings.py into the owning packages' settings.py so the vendor package keeps only the transport fields its client needs, and deletes packages/aws_platform together with the legacy modules. Decompose into per-feature subtasks at planning time. Do not start before TASK-25.2 is Done.

EVENTUAL HOMES (recorded 2026-09-11 so the Google-series pattern of vendor-neutral infrastructure services for workplace concerns, see decisions/workplace-systems.md, is not repeated):
- Identity Center holds people's AWS accounts. A shared Identity Center adapter goes to a capability package (decisions/plugin-architecture.md; likely the people-and-accounts capability, decisions/people-and-accounts.md), promoted only when the second feature actually needs it. Never infrastructure/.
- Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security Hub and Lambda are Path B adapters (decisions/plugin-architecture.md): the feature exists to act on AWS, so each adapter lives inside its feature. Promote to a capability package only if a second feature needs the same operation, with the justification recorded.
- DynamoDB is a hosting service. The thin adapter TASK-25.2.5 builds is a seam; its callers move onto the storage contract resolved from the service registry (with the TASK-27 storage redesign), and the seam is deleted.
- No new app/infrastructure/<service>/ Protocol is created for any of these.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Feature boundaries for the former modules/aws, modules/provisioning and AWS jobs are decided and recorded against the TASK-36 inventory, with one subtask per feature, each rebuilt in app/features/<feature>/
- [ ] #2 Every adapter under packages/aws_platform/adapters/ lives in its eventual home (the owning feature's adapters/, a capability with a recorded second-feature justification, or the storage contract for DynamoDB callers) and returns typed domain values; no new infrastructure/<service> Protocol was introduced
- [ ] #3 packages/aws_platform, modules/aws, modules/provisioning and the migrated jobs are deleted
- [ ] #4 Feature-level AWS settings (permission sets, role ARNs, SSO instance, SERVICE_ROLE_MAP) move from integrations/aws/settings.py into the owning features' settings slices (values in the TOML files); integrations/aws/settings.py keeps only the transport fields the client itself needs
- [ ] #5 The packages/aws_platform seam guard retires with the package: app/bin/check_aws_platform_seam.py, app/bin/baselines/aws_platform_seam_consumers.txt and the make check-aws-platform-seam target are deleted once the baseline is empty (TASK-25.2.5.5 created them)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:05
---
2026-09-14 (human decision): the AWS access-request flow (aws_access_requests.py, jobs/revoke_aws_sso_access.py) was removed from the feature inventory. It is dead and deleted under TASK-25.2.3.2.4, and packages/access re-provides the capability. ops_group_assignment.py stays in the inventory as its own concern.
---
<!-- COMMENTS:END -->
