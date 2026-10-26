---
id: TASK-169
title: >-
  Design session: Google Workspace credential model (domain-wide delegation,
  scopes per caller, keyless federation from ECS)
status: To Do
assignee: []
created_date: '2026-10-26T18:40:00Z'
updated_date: '2026-10-26T18:52:00Z'
labels:
  - security
  - configuration
milestone: m-7
dependencies: []
references:
  - decisions/service-accounts.md
  - decisions/configuration.md
  - >-
    https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices
type: feature
ordinal: 447000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-26 while planning TASK-111.10. Today one GCP service account (project cdssnc) holds a downloaded JSON key with domain-wide delegation and, by default, impersonates one Workspace user (SRE_BOT_EMAIL, a cds-snc.ca user) for every Google call: drive (full), documents, spreadsheets, calendar, meetings.space.created and the Admin SDK directory scopes, including admin.directory.group.member (write). Domain-wide delegation lets that key impersonate any user of the domain within the authorized scopes. Google's best practices: avoid domain-wide delegation when a direct service-account grant works, restrict scopes, host the account in a dedicated project, avoid service-account keys (not needed for delegation: signJwt), restrict key creation by organisation policy. decisions/service-accounts.md already requires one least-privilege credential per role and a documented service identity per vendor; nothing applies it to Google.

History (human, 2026-10-26): before the service account, the bot used a specific admin user's OAuth token stored as a pickle string; traces remain (TF_VAR_google_oauth_pickle_string in tf_plan.yml and tf_apply.yml fed by the Actions secret GOOGLE_PICKLE_STRING, read by no terraform variable; the unused Authlib and google-auth-oauthlib dependencies; *.pickle, token.json and credentials.json in .gitignore). The current setup grew around a constraint: the GCP side uses no-cost services only, and not every API was enabled, which led to the present mix. User delegation was identified as needed for some calls (perhaps calendar or Drive folders); which ones is to be established here.

The session reviews what Google Workspace, GCP and Google Cloud Identity offer today at no cost (APIs that can be enabled, admin roles assignable to a service account, shared-drive and calendar membership, Workload Identity Federation from AWS, signJwt), and decides, per caller, the simplest arrangement that works: the principal (service account with an assigned admin role or a resource membership, or a delegated user, and which user), the minimum scopes, keyless authentication from the ECS task role instead of the JSON key where feasible, the dedicated project and organisation policies, and the Admin console and GCP steps. Constraints: no paid services; production stays up throughout (expand, migrate, contract; each step one revert); prefer few, small changes over a complete redesign. Then it amends the ADRs and re-cuts the implementation tasks. Human-led; may run while a row waits on review; before TASK-145.6, whose adapters take the delegation subject.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An inventory of every Google call site: API, scope, principal (service account or delegated user), and why that principal is needed
- [ ] #2 A decision record amendment (service-accounts.md or a Google section of workplace-systems.md) states, per role, the principal, minimum scopes, authentication (keyless where feasible, verified against the google-auth AWS supplier on ECS) and the Workspace and GCP admin steps, with current Google sources
- [ ] #3 The Google service identity section exists in integrations/google_workspace/README.md (identity, credential type, scopes, owner, rotation), as service-accounts.md rule 3 requires
- [ ] #4 Implementation tasks are created or re-scoped (tenant entry shape, key retirement, scope changes) and placed in doc-11
- [ ] #5 The no-cost availability review is recorded with current Google sources: which Workspace, Admin SDK, Cloud Identity and GCP features the plan relies on, whether each needs an API enabled or a paid tier, and what the project has enabled today
- [ ] #6 Every call that needs a delegated user is named with the reason (an API that refuses service-account tokens, or data that must belong to a user), and every other call moves off delegation or has a recorded reason to stay
- [ ] #7 The pickle-string OAuth path is confirmed unused end to end, and its remaining traces are assigned for deletion (TF_VAR_google_oauth_pickle_string and GOOGLE_PICKLE_STRING in TASK-111.15.2, Authlib and google-auth-oauthlib in TASK-111.10.2)
<!-- AC:END -->
