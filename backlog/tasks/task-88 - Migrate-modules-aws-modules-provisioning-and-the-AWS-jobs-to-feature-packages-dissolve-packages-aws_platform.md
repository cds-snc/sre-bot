---
id: TASK-88
title: >-
  Rebuild the modules/aws and modules/provisioning surfaces and the AWS jobs
  into app/features/; dissolve packages/aws_platform
status: To Do
assignee: []
created_date: 2026-09-11 15:36
updated_date: '2026-10-28T17:05:00Z'
labels:
  - phase-5
dependencies:
  - TASK-25.2
  - TASK-36.1.3
  - TASK-36.3
  - TASK-109
  - TASK-114
  - TASK-145.9
  - TASK-37.4
references:
  - decisions/feature-packages.md
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
  - app/modules/aws
  - app/modules/provisioning
  - app/integrations/aws/settings.py
  - decisions/plugin-architecture.md
  - decisions/migration.md
  - decisions/authorization.md
  - https://github.com/cds-snc/sre-bot/issues/1641
priority: medium
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/aws and modules/provisioning hold several business features with mixed concerns: AWS Ops group assignment (ops_group_assignment.py), AWS account health reporting (aws_account_health.py), spending reports (spending.py), Lambda inventory (lambdas.py), and Identity Center user/group administration (identity_center.py, users.py, groups.py, aws.py), which overlaps modules/provisioning/{users,groups}.py and the disabled packages/access feature. Their AWS SDK calls sit behind packages/aws_platform/adapters/, a provisional adapters-only package that is neither a feature nor a capability package. The AWS jobs are provision_aws_identity_center and the spending data update in jobs/scheduled_tasks.py (pinned by TASK-36.3), plus the AWS probe in integration_healthchecks (scheduled_tasks.py:142), whose survival TASK-127 decides; only its call path moves here.

Rules (decisions/plugin-architecture.md, migration.md):
- Rebuilt by surface (TASK-36 inventory: target, pin, rebuild, cutover), not migrated as modules. The commands and interactions are pinned by TASK-36.1.3.
- Each business feature lands in app/features/<feature>/ with its Path B adapters in its own adapters/.
- A shared Identity Center adapter goes to a capability in app/capabilities/ only when a second feature needs it (people-and-accounts, TASK-83, decisions/people-and-accounts.md, is the likely home). Never infrastructure/.
- Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security Hub and Lambda are Path B adapters: the feature exists to act on AWS, so each adapter lives inside its feature. Promote to a capability only if a second feature needs the same operation, with the justification recorded.
- DynamoDB is a hosting service: its callers move onto the records contract resolved from the service registry, and the seam is deleted.
- No new app/infrastructure/<service>/ Protocol is created.
- The rebuilt AWS surfaces declare permissions and get roles from the central configuration (decisions/authorization.md); modules/permissions (is_user_member_of_groups) and the AWS_ADMIN_GROUPS setting are deleted, not carried over.

Out of scope: the AWS account access-request flow; packages/access re-provides it.

packages/aws_platform can only be dissolved once its other consumers leave the seam (bin/baselines/aws_platform_seam_consumers.txt): incident persistence (modules/incident/db_operations.py) in TASK-145.9 and the webhook CRUD (modules/slack/webhooks.py) in TASK-37.4.

This task decides the feature boundaries per decisions/feature-packages.md and decisions/plugin-architecture.md, rebuilds each surface with the standard feature-package recipe (TASK-145 and TASK-39 are the incident and small-module precedents), moves each adapter into its owning home, types adapter returns as frozen domain dataclasses (decisions/sdk-typing.md item 3), relocates the feature-level AWS settings (permission sets, role ARNs, SSO instance, service_role_map; integrations/aws/settings.py:104-124) into the owning features' settings slices so the vendor package keeps only the transport fields its client needs, moves the aws_ops values out of infrastructure/configuration/features/aws_ops.py, and deletes packages/aws_platform together with the legacy modules. Decompose into per-feature subtasks at planning time.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Feature boundaries for the former modules/aws, modules/provisioning and AWS jobs are decided and recorded against the TASK-36 inventory, with one subtask per feature, each rebuilt in app/features/<feature>/
- [ ] #2 Every adapter under packages/aws_platform/adapters/ lives in its eventual home (the owning feature's adapters/, a capability with a recorded second-feature justification, or the records contract for DynamoDB callers) and returns typed domain values; no new infrastructure/<service> Protocol was introduced
- [ ] #3 packages/aws_platform, modules/aws, modules/provisioning and the migrated jobs are deleted
- [ ] #4 Feature-level AWS settings (permission sets, role ARNs, SSO instance, SERVICE_ROLE_MAP) move from integrations/aws/settings.py into the owning features' settings slices (values in the TOML files); integrations/aws/settings.py keeps only the transport fields the client itself needs
- [ ] #5 The packages/aws_platform seam guard retires with the package: app/bin/check_aws_platform_seam.py, app/bin/baselines/aws_platform_seam_consumers.txt and the make check-aws-platform-seam target are deleted once the baseline is empty (TASK-25.2.5.5 created them)
- [ ] #6 The spending sheet id move from the interim [google_resources] table into the aws spending feature slice's table in the configuration files, and GoogleResourcesConfig stops exposing them
- [ ] #7 modules/permissions and the AWS_ADMIN_GROUPS setting ([cloud_operations] aws_admin_groups, moved onto the files by TASK-111.14; the table is named for the product area because AWS_* environment names are the SDK's) are deleted with the table and infrastructure/configuration/features/aws_ops.py; the rebuilt AWS surfaces declare their permissions per decisions/authorization.md, and any key a rebuilt slice keeps is standardised (lower snake_case, no table-name repeat)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 (decisions/authorization.md): the rebuilt AWS surfaces declare permissions and get roles from the central configuration. modules/permissions is_user_member_of_groups and the AWS_ADMIN_GROUPS setting are deleted, not carried over.
<!-- SECTION:NOTES:END -->
