---
id: TASK-111.15.2
title: 'Contract 2: remove the SSM blob IAM read and the old GCP key parameter'
status: To Do
assignee: []
created_date: '2026-10-22T13:57:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.15.1
references:
  - terraform/iam.tf
  - terraform/ssm.tf
  - .github/workflows/tf_plan.yml
  - .github/workflows/tf_apply.yml
  - decisions/configuration.md
parent_task_id: TASK-111.15
priority: medium
type: feature
ordinal: 430000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second half of TASK-111.15, after the TASK-111.15.1 deploy is verified. Removes the IAM read on sre-bot-config and sre-bot-config-infrastructure, the old gcp_sre_service_account_key parameter's terraform resource and variable (its value sits in terraform state today) and the TF_VAR_gcp_sre_service_account_key lines in tf_plan.yml and tf_apply.yml. Human, after merge: delete both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret. Delivers TASK-54 AC3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The IAM policy no longer grants read on sre-bot-config or sre-bot-config-infrastructure
- [ ] #2 The old gcp_sre_service_account_key resource and variable are gone, and no TF_VAR_gcp_sre_service_account_key line remains in tf_plan.yml or tf_apply.yml
- [ ] #3 The PR's tf plan shows only the IAM and parameter removals; nothing replaced
- [ ] #4 TASK-54's AC3 is checked and TASK-54 is set to Done in this PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human: both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret are deleted after the deploy is verified
<!-- DOD:END -->
