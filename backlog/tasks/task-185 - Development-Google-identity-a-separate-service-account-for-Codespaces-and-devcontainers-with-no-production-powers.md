---
id: TASK-185
title: >-
  Development Google identity: a separate service account for Codespaces and
  devcontainers, with no production powers
status: To Do
assignee: []
created_date: '2026-11-05T21:17:00Z'
updated_date: '2026-11-05T22:11:00Z'
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
- Every developer who runs the bot needs this identity. The local configuration switches the Slack transport on, and while the legacy incident handlers are registered the host fails boot without a Google tenant (server/configuration/host_configuration.py, validate_legacy_incident_google_tenant, until TASK-145.13). The incident.response and incident.scribe plugins, enabled in base.toml, also declare google_workspace.tenant as a requirement, and an unmet requirement stops boot. That is by design, not a gap: decisions/incident-management.md (System selection) requires an enabled incident feature to resolve a workplace system for a new incident's report and video call, and keeps no in-app editor. TASK-145.7 AC #9 replaces the plugin's hard-coded google_workspace.tenant with that policy, resolved through the configured-systems read. A second suite is the unscheduled expansion DRAFT-6. Local runs therefore use a real development tenant, as they already do for every other vendor in config/local.toml (the development Slack app, the shared model gateway, the Opsgenie development key), following twelve-factor dev/prod parity: the same backing services in development and production. Running without Google means switching the transport and the incident plugins off, which is not a useful default. Unit and integration tests need no Google: they use fakes and blank tenant variables (decisions/testing.md).
- Because every developer needs it, onboarding must be one step for them (joining the group) plus the gcloud login, with no GCP console visit and no per-person GCP grant.
- A development service account in a small dedicated project (for example sre-bot-dev), not in cdssnc: no key, no domain-wide delegation entry, Content manager of a test shared drive only, at most a read-only directory admin role. No developer grant lands in cdssnc, which hosts other teams' accounts.
- Access is a Workspace group (for example sre-bot-developers@). roles/iam.serviceAccountTokenCreator is bound on the development account (resource level, not a project role) to that group, so onboarding and offboarding are group membership, and a suspended account loses access with no GCP step.
- Workspace side, by a super admin: Admin console > Apps > Additional Google services > Google Cloud Platform turned on for that group only (it grants no permission by itself), and Security > API controls checked so Google Cloud is not restricted for it.
- Quota project, standard rather than conditional (human, 2026-11-05: developers may get low-risk GCP access when it is scripted): the group holds roles/serviceusage.serviceUsageConsumer on the development project, and the developer script sets that project as the ADC quota project. The role only lets their calls count against the project's quota for APIs already enabled there; it reads no data, and the project has no billing account. These two group bindings are the developers' only GCP access.
- Nothing in the code changes. The Codespace's GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account, and the file ids point at the test drive. Meetings cannot run locally without delegation; they use fakes or a separately approved test entry.

Scripted, not documented as console steps (repo-root bin/, developer helpers outside the image, like deploy-checks):
- bin/google-dev-identity.zsh, run once by a project owner, idempotent:
  - setup: the APIs on the development project, the development account if absent, and the group's two bindings; it prints the account email for the Codespaces secret;
  - check (read-only): prints the account, its keys (must be none) and both bindings.
  The development project, the Workspace group and the Admin console Google Cloud switch for that group are one-time super-admin steps it names but does not perform.
- bin/google-dev-login.zsh, run by each developer from a make target (make google-login):
  - checks gcloud;
  - runs gcloud auth application-default login --no-launch-browser if no login is present;
  - sets the quota project;
  - checks impersonation of GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL by requesting a token without printing it;
  - reports OK or the failing step with its fix (not in the group, Google Cloud off for the group, no login).
  It never writes a key and never prints a token.

The task starts with a short test: one developer with only Workspace access, in a fresh Codespace, runs the login script against the account the setup script created. Its outcome is recorded before the runbook is finalised.

Rejected: a key for the development account in a Codespaces secret. It is the copied key rule 5 forbids, shared by every developer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Test first: a developer with only Google Workspace access, in a fresh Codespace, runs make google-login against the development account created by the setup script; the outcome (Google Cloud on for the group, group grants effective, quota project accepted) is recorded in the task notes before the runbook is finalised
- [ ] #2 A development service account exists in a dedicated development project with no key, no domain-wide delegation entry, Content manager on a test shared drive and at most a read-only directory admin role; recorded in the README service identity section (no live scopes of the production entry written anywhere)
- [ ] #3 roles/iam.serviceAccountTokenCreator on the development account and roles/serviceusage.serviceUsageConsumer on the development project are bound to the Workspace group only (no individual binding, nothing in cdssnc); nobody outside the deployment holds Token Creator on the production account; Data Access audit logs are on for the IAM Service Account Credentials API on both accounts' projects
- [ ] #4 Google Cloud Platform is turned on in the Admin console for the developers' group only, and API controls do not restrict Google Cloud for it; recorded in the runbook (who sets it, where)
- [ ] #5 Codespaces secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL names the development account, and the Codespace's Google file ids point at the test drive (env-checks plan and apply); the Codespaces key secret is no longer needed by any Codespace (TASK-182 deletes it)
- [ ] #6 The runbook's local section and the root README state that every local run with the Slack transport or the incident plugins needs the development identity (and why, until TASK-145.13 and while the incident plugins require Google), then walk a new developer from a fresh Codespace or devcontainer to a booting bot: joining the group, the login, what does not work locally (meetings), and what leaving the team means (group removal)
- [ ] #7 bin/google-dev-identity.zsh (setup idempotent, check read-only) and bin/google-dev-login.zsh with a make google-login target exist; neither writes a key nor prints a token or secret; running setup twice changes nothing; the login script names the failing step and its fix; both pass shellcheck
- [ ] #8 A new team member follows the documentation unaided, and every place they got stuck is corrected in the docs
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T22:04:00Z

---

2026-11-05 (human): scope revised; developers have Workspace access only. Group-bound Token Creator on the account, a dedicated development project, Google Cloud on for that group only, a quota project only if a test shows it is needed, local Google optional. The test runs first.

---

created: 2026-11-05T22:07:00Z

---

2026-11-05 (human): correction; local Google is not optional. The Slack transport (legacy incident rule until TASK-145.13) and the incident.response and incident.scribe plugins require the Google tenant at boot, so every developer needs the development identity. AC #6 reworded.

---

created: 2026-11-05T22:09:00Z

---

2026-11-05 (human): developers may get low-risk GCP access when it is scripted. Service Usage Consumer on the development project is now standard, and setup and login are scripts (new AC #7).

---

created: 2026-11-05T22:11:00Z

---

2026-11-05: program-scope reassessment. Incident needing a workplace system is settled by incident-management.md (System selection; TASK-145.7 AC #9), and local runs use real development tenants for every vendor (config/local.toml; twelve-factor dev/prod parity). No ADR change.

---
<!-- COMMENTS:END -->
