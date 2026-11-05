---
id: TASK-185
title: >-
  Development Google identity: a separate service account for Codespaces and
  devcontainers, with no production powers
status: To Do
assignee: []
created_date: '2026-11-05T21:17:00Z'
updated_date: '2026-11-05T22:04:00Z'
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
Found while planning TASK-180 (2026-11-05); scope revised the same day after the human noted that developers hold only basic Google Workspace access, no GCP access.

After TASK-180, a developer authenticates with their own gcloud login and impersonates a service account (service-accounts.md rule 5). If that account were the production one, the grant would let a laptop mint tokens as the bot and, through signJwt, delegated tokens for any user the delegation entry covers. This task gives local runs their own identity instead.

Shape:
- Local Google is optional. With no tenant entry Google is off and the bot runs standalone; feature tests use the in-memory fakes. Only developers working on Google adapters run against Google, and the documentation says so first.
- A development service account in a small dedicated project (for example sre-bot-dev), not in cdssnc: no key, no domain-wide delegation entry, Content manager of a test shared drive only, at most a read-only directory admin role. No developer grant lands in cdssnc, which hosts other teams' accounts.
- Access is a Workspace group (for example sre-bot-developers@). roles/iam.serviceAccountTokenCreator is bound on the development account (resource level, not a project role) to that group, so onboarding and offboarding are group membership, and a suspended account loses access with no GCP step.
- Workspace side, by a super admin: Admin console > Apps > Additional Google services > Google Cloud Platform turned on for that group only (it grants no permission by itself), and Security > API controls checked so Google Cloud is not restricted for it.
- Quota project: user credentials may need a quota project (serviceusage.services.use) to call IAM Credentials. If the test shows it, the group gets roles/serviceusage.serviceUsageConsumer on the development project only.
- Nothing in the code changes. The Codespace's GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account, and the file ids point at the test drive. Meetings cannot run locally without delegation; they use fakes or a separately approved test entry.

The task starts with a short test, run before anything is documented as final: one developer with only Workspace access, in a fresh Codespace, logs in and makes one impersonated call. It answers whether Google Cloud is on for them, whether the group grant works, and whether a quota project is needed.

Rejected: a key for the development account in a Codespaces secret. It is the copied key rule 5 forbids, shared by every developer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Test first: a developer with only Google Workspace access, in a fresh Codespace, runs gcloud auth application-default login --no-launch-browser and one impersonated call against the development account; the outcome (Google Cloud service state for the group, group grant effective, quota project needed or not) is recorded in the task notes before the runbook is finalised
- [ ] #2 A development service account exists in a dedicated development project with no key, no domain-wide delegation entry, Content manager on a test shared drive and at most a read-only directory admin role; recorded in the README service identity section (no live scopes of the production entry written anywhere)
- [ ] #3 roles/iam.serviceAccountTokenCreator on the development account is bound to a Workspace group only (no individual and no project-level binding); nobody outside the deployment holds it on the production account; roles/serviceusage.serviceUsageConsumer on the development project is granted to the group only if the test needs it; Data Access audit logs are on for the IAM Service Account Credentials API on both accounts' projects
- [ ] #4 Google Cloud Platform is turned on in the Admin console for the developers' group only, and API controls do not restrict Google Cloud for it; recorded in the runbook (who sets it, where)
- [ ] #5 Codespaces secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account, and the Codespace's Google file ids point at the test drive (env-checks plan and apply); the Codespaces key secret is no longer needed by any Codespace (TASK-182 deletes it)
- [ ] #6 The runbook's local section and the root README say first that Google is optional locally, then walk a developer who needs it from a fresh Codespace or devcontainer to a working Google call: joining the group, the login, what does not work locally (meetings), and what leaving the team means (group removal)
- [ ] #7 A new team member follows the documentation unaided, and every place they got stuck is corrected in the docs
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T22:04:00Z

---

2026-11-05 (human): scope revised; developers have Workspace access only. Group-bound Token Creator on the account, a dedicated development project, Google Cloud on for that group only, a quota project only if a test shows it is needed, local Google optional. The test runs first.

---
<!-- COMMENTS:END -->
