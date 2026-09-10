---
id: TASK-83.3
title: >-
  Provision the people table in Terraform and the devcontainer, with no
  application consumer
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
  - storage
dependencies:
  - TASK-83.1
references:
  - terraform/dynamodb.tf
  - terraform/iam.tf
  - .devcontainer/dynamodb-create.sh
parent_task_id: TASK-83
priority: medium
ordinal: 170000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Option A in decisions/people-and-accounts.md stores people, accounts and links in a dedicated DynamoDB table owned by the people capability package. Shipping the table on its own first keeps the infrastructure change reviewable and reversible before any code reads or writes it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 terraform/dynamodb.tf defines the people table, following the file's existing conventions
- [ ] #2 The key design supports these access patterns without scans: get a person by id; get an account by (system, tenant, account_id); list a person's accounts and links; claim an account for exactly one person
- [ ] #3 The application role gets least-privilege access limited to the new table
- [ ] #4 The devcontainer creates the table locally
- [ ] #5 No application code reads or writes the table yet
<!-- AC:END -->
