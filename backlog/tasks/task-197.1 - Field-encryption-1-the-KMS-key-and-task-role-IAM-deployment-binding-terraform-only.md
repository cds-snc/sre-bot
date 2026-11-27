---
id: TASK-197.1
title: >-
  Field encryption 1: the KMS key and task-role IAM (deployment binding,
  terraform only)
status: To Do
assignee: []
created_date: '2026-11-27T16:46:00Z'
labels:
  - security
  - terraform
milestone: m-4
dependencies: []
references:
  - decisions/deployment.md
  - decisions/cloud-portability.md
parent_task_id: TASK-197
priority: high
ordinal: 557000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
doc-11 row 22.12a; a single PR from origin/main, before 22.12b. This deployment's binding for the TASK-197 contract: an aws_kms_key (symmetric, rotation enabled) with an alias, and task-role permissions kms:Encrypt, kms:Decrypt and kms:GenerateDataKey on that key only, with the key policy limited to the account root and the task role. Terraform only, so tf_apply runs and no app image deploys (deployment.md). It moves to the deployment repository with the rest of terraform/ (product-scope.md end state). The key URI is a non-secret configuration-file value that TASK-197.2 reads: no SSM name.
Blast radius: one unused key and one IAM statement. Rollback: a revert never deletes the key; removal is a removed block with lifecycle { destroy = false }, and a key is only ever scheduled for deletion by hand after every sealed value is resealed. bin/deploy-checks.zsh pre and post apply. Change notice: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 terraform declares the key with rotation enabled and an alias, and the task role gets kms:Encrypt, kms:Decrypt and kms:GenerateDataKey on that key ARN only (review + terraform plan)
- [ ] #2 The PR changes only terraform/ and its task file; terraform plan creates the key, alias and policy and destroys nothing (check)
- [ ] #3 bin/deploy-checks.zsh pre runs before the merge and post after the apply, and the output is read (human run, agent reads)
<!-- AC:END -->
