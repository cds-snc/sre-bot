---
id: TASK-88
title: >-
  Migrate modules/aws, modules/provisioning and the AWS jobs to feature
  packages; dissolve packages/aws_platform
status: To Do
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-11 15:53'
labels:
  - phase-5
dependencies:
  - TASK-25.2
references:
  - decisions/feature-packages.md
  - decisions/capability-packages.md
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
  - decisions/layers.md
  - app/modules/aws
  - app/modules/provisioning
  - app/integrations/aws/settings.py
priority: medium
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-25.2 (created 2026-09-11). modules/aws was named after a vendor but holds several business features with mixed concerns: AWS access requests (aws_access_requests.py, ops_group_assignment.py, jobs/revoke_aws_sso_access.py), AWS account health reporting (aws_account_health.py), spending reports (spending.py), Lambda inventory (lambdas.py), and Identity Center user/group administration (identity_center.py, users.py, groups.py, aws.py), which overlaps modules/provisioning/{users,groups}.py and the disabled packages/access feature. TASK-25.2 isolates their AWS SDK calls behind packages/aws_platform/adapters/, a provisional adapters-only package that is neither a feature nor a capability package.

This task decides the feature boundaries per decisions/feature-packages.md and decisions/capability-packages.md, migrates each module with the standard feature-package recipe (TASK-38 and TASK-39 are the incident and small-module precedents), moves each adapter into its owning home, types adapter returns as frozen domain dataclasses (decisions/sdk-typing.md item 3), relocates the feature-level AWS settings (permission sets, role ARNs, SSO instance, SERVICE_ROLE_MAP) out of integrations/aws/settings.py into the owning packages' settings.py so the vendor package keeps only the transport fields its client needs, and deletes packages/aws_platform together with the legacy modules. Decompose into per-feature subtasks at planning time. Do not start before TASK-25.2 is Done.

EVENTUAL HOMES (recorded 2026-09-11 so the Google-series pattern of vendor-neutral infrastructure services for workplace concerns, see decisions/workplace-systems.md, is not repeated):
- Identity Center holds people's AWS accounts. A shared Identity Center adapter goes to a capability package (decisions/capability-packages.md; likely the people-and-accounts capability, decisions/people-and-accounts.md), promoted only when the second feature actually needs it. Never infrastructure/.
- Organizations, SSO-Admin, Config, Cost Explorer, GuardDuty, Security Hub and Lambda are Path B adapters (decisions/layers.md): the feature exists to act on AWS, so each adapter lives inside its feature. Promote to a capability package only if a second feature needs the same operation, with the justification recorded.
- DynamoDB is a hosting service. The thin adapter TASK-25.2.5 builds is a seam; its callers move onto the existing infrastructure/storage Protocol (with the TASK-27 storage redesign), and the seam is deleted.
- No new app/infrastructure/<service>/ Protocol is created for any of these.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Feature boundaries for the former modules/aws, modules/provisioning and AWS jobs are decided and recorded, with one subtask per feature package
- [ ] #2 Every adapter under packages/aws_platform/adapters/ lives in the eventual home stated in the description (feature adapter, capability package with second-feature justification, or infrastructure/storage for DynamoDB callers) and returns typed domain values; no new infrastructure/<service> Protocol was introduced
- [ ] #3 packages/aws_platform, modules/aws, modules/provisioning and the migrated jobs are deleted
- [ ] #4 Feature-level AWS settings (permission sets, role ARNs, SSO instance, SERVICE_ROLE_MAP) move from integrations/aws/settings.py into the owning packages' settings.py; integrations/aws/settings.py keeps only the transport fields the client itself needs
<!-- AC:END -->
