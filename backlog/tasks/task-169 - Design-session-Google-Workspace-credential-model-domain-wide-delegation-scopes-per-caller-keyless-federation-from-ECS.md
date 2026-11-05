---
id: TASK-169
title: >-
  Design session: Google Workspace integration shape and credential model
  (purpose-named ports, domain-wide delegation, scopes per caller, keyless
  federation from ECS)
status: In Progress
assignee:
  - '@me'
created_date: '2026-10-26T18:40:00Z'
updated_date: '2026-11-05T00:16:00Z'
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
- [x] #1 An inventory of every Google call site: API, scope, principal (service account or delegated user), and why that principal is needed
- [x] #2 A decision record amendment (service-accounts.md or a Google section of workplace-systems.md) states, per role, the principal, minimum scopes, authentication (keyless where feasible, verified against the google-auth AWS supplier on ECS) and the Workspace and GCP admin steps, with current Google sources
- [x] #3 The Google service identity section exists in integrations/google_workspace/README.md (identity, credential type, scopes, owner, rotation), as service-accounts.md rule 3 requires
- [x] #4 Implementation tasks are created or re-scoped (tenant entry shape, key retirement, scope changes) and placed in doc-11
- [x] #5 The no-cost availability review is recorded with current Google sources: which Workspace, Admin SDK, Cloud Identity and GCP features the plan relies on, whether each needs an API enabled or a paid tier, and what the project has enabled today
- [x] #6 Every call that needs a delegated user is named with the reason (an API that refuses service-account tokens, or data that must belong to a user), and every other call moves off delegation or has a recorded reason to stay
- [x] #7 The pickle-string OAuth path is confirmed unused end to end, and its remaining traces are assigned for deletion (TF_VAR_google_oauth_pickle_string and GOOGLE_PICKLE_STRING in TASK-111.15.2, Authlib and google-auth-oauthlib in TASK-111.10.2)
- [x] #8 The integration shape is decided and written into the tasks: integrations/google_workspace/ is the one Google gateway (client factories with their credentials and delegation, tenant, retries, error classification; no shared helpers, per outbound-clients.md, human 2026-11-05); the people directory is the Google-backed workplace capability (TASK-119); TASK-120 and 121 are re-scoped to purpose-named ports owned by their consumers (incident report through TASK-145.6, talent role folders, AWS spending, the incident list projection), and TASK-138 is held or re-scoped, each with its reason
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26 (human approved): integration shape folded in. The session also confirms which Google-backed operations are workplace capabilities (the people directory, TASK-119, confirmed by its ~14 consumers and Microsoft Entra beside Google) and which become purpose-named ports owned by their consumers over integrations/google_workspace/ (drive and spreadsheets: TASK-120, 121; calendar: TASK-138 held), per decisions/workplace-systems.md as amended 2026-10-26. Lands before TASK-120, 121, 138 and 145.6 (dependencies added); TASK-119 does not wait on it.

2026-11-04 session evidence (prepared before the decisions; full tables in the session scratchpad, condensed here).

AC1 inventory. Principal mechanics: integrations/google_workspace/client.py:186-189 applies `delegated_user_email or tenant.delegated_user_email` with with_subject, then with_scopes; scopes are per call (no global list); from_service_account_info only at settings.py:52 (boot shape check). Every production call runs as the one tenant subject (GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL); talent passes the same value explicitly; no caller passes another user; no code comment states why a subject is used. Roles found:
- R1 people directory read: infrastructure/directory/google.py customers.get :402, users.get :426, users.list :463, members.list :515/:582/:858, groups.get :609, members.hasMember :727, groups.list :771/:911; scopes admin.directory.{customer,user,group,group.member}.readonly; callers access request and sync, modules/provisioning, modules/permissions, modules/dev, lifespan warmup.
- R2 group membership write: members.insert :650, members.delete :700; scope admin.directory.group.member; caller packages/access/request/service.py:393,395,564,566,827,829.
- R3 incident documents and folders: features/incident/drive/adapters/google_drive.py files.update appProperties :108/:118, files.get :127, list/create folder/copy template via infrastructure/drive (files.list corpora=user with allDrives, files.create, files.copy); features/incident/documents/adapters/google_docs.py get :66, batchUpdate :47/:99; scribe/adapters/google_docs.py get :155/:232, batchUpdate :259, files.copy :327, files.get :1328; scopes drive (full), documents; supportsAllDrives everywhere.
- R4 talent role folders: packages/talent/adapters/google_drive.py files.create :32, files.copy plus addParents :47; scope drive; parent TALENT__INTERNAL_FOLDER_ID.
- R5 sheets projections: modules/incident/incident_folder.py values.append :304, values.get :337, spreadsheets.get :415 (INCIDENT_CORE__LIST_SHEET_ID); modules/aws/spending.py:242 values.batchUpdate (CLOUD_OPERATIONS_SPENDING__SHEET_ID); scope spreadsheets (full).
- R6 meeting scheduling: features/incident/scheduling/adapters/google_calendar.py freebusy.query :46, events.insert :103-110 (attendees, sendUpdates=all, conferenceData hangoutsMeet; calendarId INCIDENT_POSTMORTEM__CALENDAR_ID or primary); scope calendar (full).
- R7 incident meeting space: features/incident/meet/adapters/google_meet.py spaces.create :26; scope meetings.space.created; callers modules/incident/core.py:131,:459.
Unknown from the repo (Admin console and Drive checks): which admin roles the subject holds; whether the folder, template and sheet ids sit in a shared drive or the subject's My Drive; the DWD scope list granted (no record anywhere); the GCP project id (task text says cdssnc). .env.example is behind a deny rule and was not read.

AC5 no-cost review (sources read 2026-11-04): IAM is free, covering WIF pools and providers, service accounts, generateAccessToken and signJwt ("All use of Identity and Access Management API is free of charge", https://cloud.google.com/iam/pricing). STS token exchange has no published price (human check: no Cloud Billing SKU). APIs to enable: iam, iamcredentials, sts, cloudresourcemanager (https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds) plus the Workspace APIs in use. Drive, Docs, Sheets, Calendar and Meet: standard use at no additional cost, but over-quota use "is planned to incur charges ... later in 2026" with 90 days' notice (each API's usage-limits page). Admin SDK and Cloud Identity: no price published; included with Workspace (unverified wording). Admin-role assignment to a service account: any prebuilt or custom role except Super Admin (https://developers.google.com/workspace/guides/create-credentials); assignments count toward 1,000 (https://knowledge.workspace.google.com/admin/users/assign-specific-admin-roles). Shared drives: a service account has no storage quota and cannot own files, so files must go in shared drives (https://developers.google.com/workspace/drive/api/guides/about-shareddrives). Quotas: STS 6,000/min, generateAccessToken and signJwt 60,000/min each per project (https://docs.cloud.google.com/iam/quotas); Meet spaces.create 100/min/project. Library: locked google-auth 2.62.0 has aws.AwsSecurityCredentialsSupplier (needs >=2.29) and impersonated_credentials.Credentials(subject=...) (keyless DWD via signJwt, >=2.56.1); verified on the installed package. The built-in AWS source reads IMDS or env vars only, never the ECS container credentials endpoint (google-auth aws.py), and Fargate has no instance profile (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html), so a boto3-backed supplier is required (Google's sample: https://docs.cloud.google.com/iam/docs/authenticate-with-auth-libraries).

AC6 delegated-user needs: Calendar attendees need DWD ("Service accounts need to use domain-wide delegation of authority to populate the attendee list", https://developers.google.com/workspace/calendar/api/v3/reference/events); Meet REST accepts user authentication only, DWD counts (https://developers.google.com/workspace/meet/api/guides/authenticate-authorize). Directory reads and group writes work with an admin role assigned to the service account, no DWD (create-credentials page above); Drive, Docs and Sheets work through shared-drive membership. DWD cannot be limited to users or OUs and can impersonate super admins (https://knowledge.workspace.google.com/admin/apps/control-api-access-with-domain-wide-delegation, https://docs.cloud.google.com/iam/docs/best-practices-service-accounts).

AC7 pickle path: unused end to end. No code, terraform variable or workflow reads GOOGLE_PICKLE_STRING, TF_VAR_google_oauth_pickle_string, token.json, credentials.json, InstalledAppFlow, google_auth_oauthlib, Authlib, oauth2client or from_authorized_user. tf_plan.yml:12 and tf_apply.yml:15 carry only TF_VAR_slack_webhook_url (removed by TASK-111.15.2); Authlib and google-auth-oauthlib are absent from pyproject.toml and uv.lock (removed by TASK-111.10.2). Traces left: app/bin/audit_env_names.py:70 RETIRED entry and its test parameter (retirement evidence, kept by design); .gitignore:217,218,226 (*.pickle, token.json, credentials.json: guards against committing credentials). The Actions secret GOOGLE_PICKLE_STRING could not be listed (gh secret list: HTTP 403); a human confirms it is deleted.

2026-11-05 decisions (human approved, after a clarification round on how the Google pieces fit and on per-user attribution):
- D0: the bot always acts as itself, never as the requesting person. Evidence: no call passes another user; the floppy_disk timeline entry names the person in the text and writes as the bot (modules/incident/incident_conversation.py:292-312). Dispatch delegates to one fixed account (dispatch_google config.py, common.py with_subject(service_account_delegated_account)). The delegation entry is large because every call delegates, not because of per-user attribution.
- D1: keyless Workload Identity Federation from the ECS task role (sre-bot-ecs-role) to the EXISTING service account, so the client id, delegation entry, shared-drive membership and Drive appProperties (private to the OAuth client id) are unchanged; boto3-backed AwsSecurityCredentialsSupplier; signJwt delegation via impersonated_credentials(subject=...). Developers use gcloud application-default login plus a per-person Token Creator grant.
- D2: one service account for every role (same workload, so separate accounts would not separate holders; the per-call scoped token is the credential per role). Directory read and group write: the account with the bot user's admin role (Users read, Groups read and update) assigned. Drive, Docs, Sheets: the account itself, already Content manager on the SRE shared drive (human). Delegation only for Calendar attendees and Meet: calendar.events, calendar.freebusy, meetings.space.created; the bot user keeps no admin role.
- The human showed the current delegation entry; at their request its scope list is recorded nowhere. It holds scopes no bot code requests; its name ("CDS-SNC Apps") suggests other applications may share the account, so TASK-182 and TASK-183 make sole use a precondition.
- D3: the tenant entry adds GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL (non-public) and GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE, from the environment like the rest of the Google entry (the session first said production.toml for the audience; the environment keeps one source for the entry); DELEGATED_USER_EMAIL becomes the meetings organiser. Scenarios walked: CDS on ECS (federation), Codespace (gcloud ADC), adopter on GCP (ADC), adopter without meetings (no delegation at all), second Google tenant (a list of entries, unchanged per entry), Entra beside Google (unaffected).
- D4: cdssnc hosts the pool and the account; no project-wide organisation policies there (other teams' accounts); key admin limited by IAM. Adopters use a project they control.
- D5: the gateway follows outbound-clients.md (factories, classifier, settings; credentials and delegation inside client construction; no shared helpers, AC #8 reworded). TASK-120 dissolves infrastructure/drive (after 145.6); TASK-121 deletes infrastructure/spreadsheets after 145.12 and 88 own their sheet ports (ACs added there; 145.12 no longer waits on 121); TASK-138 superseded (calendar and meet stay incident-owned; TASK-145.10 retitled and no longer waits on 138; a human archives 138).
- D6: TASK-145.6 no longer waits on TASK-169; AC #7 added (no subject or credentials in its adapters).
- D7: TASK-180 (federation), TASK-181 (only meetings delegate, after 145.6), TASK-182 (key retirement; discharges TASK-176 AC #2, since the human confirmed the SSM key is the old gcp_sre_service_account_key value), TASK-183 (delegation contract). doc-11 rows 9.10b.1, 9.10b.2, 14a, 14b.
Also: the google deploy check no longer exists (deleted in TASK-111.12.1); TASK-180 adds one, TASK-183 deletes it. Adopter setup (human request): docs/runbooks/set-up-google-workspace-access.md, per governance.md (procedures in docs/runbooks/); service-accounts.md rule 3 now puts admin steps in a linked runbook.

Files changed (no code): decisions/service-accounts.md (rule 5, Consequences, Checks, Migration, Changes, scope), decisions/workplace-systems.md (Migration, Changes), decisions/configuration.md (Migration tickets, Changes), app/integrations/google_workspace/README.md (new), docs/runbooks/set-up-google-workspace-access.md (new). Verification: app/bin/check_vendor_package_contract.py OK (README is not a .py file); no Python changed, so no ruff, mypy or pytest run.

Human: confirm the Actions secret GOOGLE_PICKLE_STRING is deleted (gh secret list returns 403 for the agent); confirm STS has no Cloud Billing SKU; archive TASK-138; move TASK-169 to Done.
<!-- SECTION:NOTES:END -->
