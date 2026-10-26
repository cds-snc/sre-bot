---
id: TASK-111.15.2
title: 'Contract 2: remove the SSM blob IAM read and the old GCP key parameter'
status: To Do
assignee: []
created_date: '2026-10-22T13:57:00Z'
updated_date: '2026-10-26T18:52:00Z'
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
  - https://github.com/cds-snc/sre-bot/issues/1779
parent_task_id: TASK-111.15
priority: medium
type: feature
ordinal: 430000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second half of TASK-111.15, after the TASK-111.15.1 deploy is verified. Removes the IAM read on sre-bot-config and sre-bot-config-infrastructure (terraform/iam.tf:32-34), the old gcp_sre_service_account_key parameter's terraform resource and variable (terraform/ssm.tf:1, variables.tf:16; its value sits in terraform state today) and the TF_VAR_gcp_sre_service_account_key lines in tf_plan.yml and tf_apply.yml. The blob's ISSUER_CONFIG key is read only by images older than TASK-111.8 and goes with sre-bot-config; it needs no separate step. Checks TASK-54's AC #3 (entry.sh fetches no SSM parameter, delivered by TASK-111.15.1). Human, after merge: delete both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret, and set TASK-54 to Done.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The IAM policy no longer grants read on sre-bot-config or sre-bot-config-infrastructure
- [ ] #2 The old gcp_sre_service_account_key resource and variable are gone, and no TF_VAR_gcp_sre_service_account_key line remains in tf_plan.yml or tf_apply.yml
- [ ] #3 The PR's tf plan shows only the IAM and parameter removals; nothing replaced
- [ ] #4 TASK-54's AC #3 is checked; TASK-54 is left for the human to set Done
- [ ] #5 bin/env-checks.zsh and app/bin/audit_env_names.py drop their migration part (SSM blob and /sre-bot parameter reads, doc-14 destinations, the baseline retired names, HINTS); the env-file, Codespaces and GitHub Actions audit stays, and its tests pass
- [ ] #6 The dead TF_VAR_google_oauth_pickle_string lines are deleted from tf_plan.yml and tf_apply.yml (no terraform variable reads them; a leftover of the pre-service-account OAuth admin user, found 2026-10-26), and the Actions secret GOOGLE_PICKLE_STRING is deleted (human, after merge)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human: both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret are deleted after the deploy is verified
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26: the env audit's SUPERSEDED map (old Google ID secrets folded into GOOGLE_RESOURCES by #975, FRONTEND_URL) goes with the migration part. GOOGLE_RESOURCES carries an unread key rep.g (folder for Google Groups reports, reader removed by #1460); TASK-158 splits GOOGLE_RESOURCES and drops it.
<!-- SECTION:NOTES:END -->
