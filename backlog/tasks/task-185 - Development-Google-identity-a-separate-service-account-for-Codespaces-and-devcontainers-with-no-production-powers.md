---
id: TASK-185
title: >-
  Development Google identity: a separate service account for Codespaces and
  devcontainers, with no production powers
status: To Do
assignee: []
created_date: '2026-11-05T21:17:00Z'
labels:
  - security
milestone: m-7
dependencies:
  - TASK-180
references:
  - decisions/service-accounts.md
  - docs/runbooks/set-up-google-workspace-access.md
  - app/integrations/google_workspace/README.md
  - >-
    https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment
priority: medium
type: feature
ordinal: 486000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while planning TASK-180 (2026-11-05). After TASK-180 a developer authenticates with their own gcloud login plus Token Creator on the service account, which the TASK-169 ruling settled (service-accounts.md rule 5). If that account is the production one, the grant lets a developer mint tokens as the bot and, through signJwt, delegated tokens for any user of the domain within the delegation entry's scopes. That is personal, revocable and audited, but it is still production power on a laptop. Codespaces hold the production key today. This task gives local runs their own identity: a development service account in cdssnc, with no domain-wide delegation entry, Content manager of a test shared drive only, and at most a read-only directory role. Developers get Token Creator on it, never on the production account. Nothing in the code changes, because the Codespace's GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account and the file ids point at the test drive. Meetings cannot be tested locally without delegation, so they use a fake or a deliberate, separately approved test entry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A development service account exists in cdssnc with no key, no domain-wide delegation entry, Content manager on a test shared drive and at most a read-only directory admin role; recorded in the README service identity section (no live scopes of the production entry written anywhere)
- [ ] #2 Each developer holds roles/iam.serviceAccountTokenCreator on the development account only; nobody outside the deployment holds it on the production account; Data Access audit logs are on for the IAM Credentials API on both accounts
- [ ] #3 Codespaces secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account, and the Codespace's Google file ids point at the test drive (env-checks plan and apply)
- [ ] #4 The runbook's local development section and the root README's local setup walk a new developer from a fresh Codespace or devcontainer to a working Google call, including what does not work locally (meetings) and how to revoke access when someone leaves
- [ ] #5 A new team member follows the documentation unaided, and every place they got stuck is corrected in the docs
<!-- AC:END -->
