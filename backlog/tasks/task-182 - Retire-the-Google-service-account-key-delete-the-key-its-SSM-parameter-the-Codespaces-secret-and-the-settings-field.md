---
id: TASK-182
title: >-
  Retire the Google service-account key: delete the key, its SSM parameter, the
  Codespaces secret and the settings field
status: To Do
assignee: []
created_date: '2026-11-05T00:09:00Z'
updated_date: '2026-11-05T00:12:00Z'
labels:
  - security
  - configuration
milestone: m-7
dependencies:
  - TASK-180
references:
  - decisions/service-accounts.md
  - decisions/configuration.md
priority: high
type: chore
ordinal: 479000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Contract step of the TASK-169 ruling (2026-11-05, human). Once production runs on the federated path (TASK-180), the JSON key is the only stored credential left that can act as the bot, and through domain-wide delegation as any user. It is the same key TASK-176 AC #2 names (human, 2026-11-05: the key in GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY is the old gcp_sre_service_account_key value), so that AC is discharged here, never before the cutover.

Precondition: the delegation entry is named "CDS-SNC Apps", so the service account and this key may serve other applications. The key is deleted only when its activity shows no authentication after the cutover, by the bot or anything else; if something else uses it, that owner is told first and this task waits.

Project-wide organisation policies on key creation are not used: cdssnc hosts other teams' service accounts (human, 2026-11-05). Key creation on the bot's account is limited through IAM instead.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The key is deleted in Google Cloud (IAM & Admin > Service accounts > the bot's account > Keys), the account holds no user-managed key, and TASK-176 AC #2 is checked with this evidence
- [ ] #2 GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY is removed from the settings slice, terraform/ssm.tf and the task definition secrets:, added to the RETIRED map in app/bin/audit_env_names.py, and the Codespaces secret of that name is deleted
- [ ] #3 The key credential source and its boot shape check are deleted; the boot shape check covers the federation entry
- [ ] #4 Only the cdssnc project owners hold iam.serviceAccountKeyAdmin on the bot's service account (no project-wide organisation policy)
- [ ] #5 decisions/configuration.md and decisions/service-accounts.md Migration record the key's removal; deploy-checks pre and post pass (a contract delete)
- [ ] #6 ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [ ] #7 Before deletion: production has run on the federated path for at least one deploy with deploy-checks post google passing (TASK-180's check), and the key's activity (GCP Policy Analyzer, service account key last authentication) shows no use after the cutover, by the bot or any other application
<!-- AC:END -->
