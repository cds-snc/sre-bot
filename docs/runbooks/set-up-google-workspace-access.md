---
title: Set up Google Workspace access for a new organisation
owner: SRE team (sre-bot maintainers)
last_reviewed: 2026-11-05
decisions:
  - decisions/service-accounts.md
  - decisions/workplace-systems.md
  - decisions/configuration.md
---

# Set up Google Workspace access for a new organisation

Use this guide when your organisation deploys the bot with Google Workspace for the first time, or when you rebuild its Google access. It takes about an hour. You need two people, or one person with both access levels:

- a **Google Cloud project owner**: someone who can create service accounts and identity pools in one project;
- a **Google Workspace super admin**: someone who can assign admin roles and manage domain-wide delegation.

You also need the AWS account id and the ECS task role name of your deployment.

What the bot's Google identity is, and its scopes, is described in [the Google Workspace package README](../../app/integrations/google_workspace/README.md#service-identity). The reasons are in [decisions/service-accounts.md](../../decisions/service-accounts.md) rule 5.

## 1. Understand the four pieces

Google identity is confusing because four separate things work together. Each one is set up in a different console.

| Piece | Plain meaning | Where it lives |
| --- | --- | --- |
| **Service account** | The bot's robot identity. It reads the directory, manages group members and works in one shared drive *as itself*. | Google Cloud console > IAM & Admin > Service accounts |
| **Workload identity pool** | Lets Google trust AWS's statement "this request comes from the bot's ECS task", so no password or key is stored anywhere. | Google Cloud console > IAM & Admin > Workload Identity Federation |
| **Bot user** | An ordinary licensed Workspace user, the organiser of the meetings the bot schedules. Google lets only a user send calendar invitations and create Meet spaces. | Admin console > Directory > Users |
| **Domain-wide delegation entry** | Permission for the robot to act as a Workspace user for a list of scopes. The bot uses it only to act as the bot user, for meetings. | Admin console > Security > Access and data control > API controls > Manage domain wide delegation |

Two warnings that most guides leave out:

- **A delegation entry is not limited to one user.** Whoever controls the service account can act as **any** account in your domain, super admins included, for every scope on the entry. Keep the entry to the three meetings scopes below and nothing else.
- **Never create a JSON key for the service account.** A key is a password that never expires and works from anywhere. With federation you don't need one.

If your organisation doesn't want the bot to schedule meetings, skip the bot user and the delegation entry entirely (steps 4 and 7). The rest still works.

## 2. Create the service account

1. In the Google Cloud console, choose the project your organisation uses for Workspace integrations, or create one. It needs no billing account: everything below is free.
2. Enable the APIs:
   ```sh
   gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
     cloudresourcemanager.googleapis.com admin.googleapis.com drive.googleapis.com docs.googleapis.com \
     sheets.googleapis.com calendar-json.googleapis.com meet.googleapis.com --project=PROJECT_ID
   ```
3. Create the account:
   ```sh
   gcloud iam service-accounts create sre-bot --project=PROJECT_ID --display-name="SRE Bot"
   ```
   Its email (`sre-bot@PROJECT_ID.iam.gserviceaccount.com`) is `SA_EMAIL` below.
4. On the account's **Details** page, note its **unique ID** (a long number). The Admin console calls it the **client ID**.

## 3. Let the bot's ECS task become the service account

1. Create the pool and the AWS provider. The condition admits only your task role. Pool and provider ids are 4 to 32 lowercase letters, digits or hyphens, so the provider is `aws-ecs`, not `aws`:
   ```sh
   gcloud iam workload-identity-pools create sre-bot --location=global --project=PROJECT_ID \
     --display-name="SRE Bot (AWS)"
   gcloud iam workload-identity-pools providers create-aws aws-ecs --location=global \
     --workload-identity-pool=sre-bot --account-id=AWS_ACCOUNT_ID --project=PROJECT_ID \
     --attribute-condition="attribute.aws_role=='arn:aws:sts::AWS_ACCOUNT_ID:assumed-role/TASK_ROLE_NAME'"
   ```
2. Let that task role, and nothing else, impersonate the service account. `PROJECT_NUMBER` is on the project's dashboard.
   ```sh
   MEMBER="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/sre-bot/attribute.aws_role/arn:aws:sts::AWS_ACCOUNT_ID:assumed-role/TASK_ROLE_NAME"
   for ROLE in roles/iam.workloadIdentityUser roles/iam.serviceAccountTokenCreator; do
     gcloud iam service-accounts add-iam-policy-binding SA_EMAIL --project=PROJECT_ID --role="$ROLE" --member="$MEMBER"
   done
   ```
3. Note the federation audience:
   `//iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/sre-bot/providers/aws-ecs`.
   It uses the project **number**, not the project id; the bot refuses to boot with any other shape.

## 4. Create the bot user (meetings only)

In the Admin console > Directory > Users, add a user such as `sre-bot@your-domain`, with a Workspace licence that includes Calendar and Meet. Give it **no admin role**. Store its password in your password manager. Nobody needs to sign in as it day to day.

## 5. Give the service account its directory role

1. Admin console > Account > Admin roles > **Create new role**, for example "SRE Bot directory". Grant these Admin API privileges:
   - Users > Read;
   - Groups > Read and Update.
2. Open the role > **Assign service accounts** > enter `SA_EMAIL`.

To let the bot manage only some groups, Google allows a Groups role to be limited to specific groups. Test that an access request can still add a member before you rely on it.

## 6. Share the bot's working files

1. Create a shared drive (for example "SRE") for incident folders, templates and sheets, or use an existing one.
2. Add `SA_EMAIL` as **Content manager**.
3. Keep every file the bot uses inside this drive: a service account cannot own files in My Drive.

If the drive is set to refuse members from outside the organisation, allow the service account explicitly: Google treats service accounts as outside your domain.

## 7. Create the delegation entry (meetings only)

Admin console > Security > Access and data control > API controls > **Manage domain wide delegation** > **Add new**:

- Client ID: the unique ID from step 2.
- OAuth scopes, exactly:
  `https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/calendar.freebusy,https://www.googleapis.com/auth/meetings.space.created`

Changes can take up to 24 hours to apply, usually a few minutes.

## 8. Configure the deployment

Set these as secret parameters of your deployment, never in a configuration file or the repository ([decisions/configuration.md](../../decisions/configuration.md)):

| Variable | Value |
| --- | --- |
| `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` | Admin console > Account > Account settings > Customer ID (never `my_customer`) |
| `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL` | `SA_EMAIL` |
| `GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE` | the audience from step 3 |
| `GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL` | the bot user from step 4; leave it unset if you skipped meetings |

A new secret parameter is added after the code that reads it is deployed, and gets its value before the next deploy ([decisions/configuration.md](../../decisions/configuration.md)): the bot rejects a variable it does not know, and a placeholder value fails its shape check. On ECS the audience is added last, as the cutover: setting it switches every task to federation at the next deploy, and removing it switches back to the key while one exists.

The bot reads `AWS_REGION` for federation; ECS on Fargate sets it.

## 8a. Run the bot locally (Codespace or devcontainer)

You run the bot as a **development** service account, never as the production one. A production grant would let your laptop act, through delegation, as any user the delegation entry covers. Until TASK-185 creates the development account, Codespaces keep using the key they have today.

1. **Check the CLI.** The devcontainer installs the Google Cloud CLI: `gcloud --version` prints a version. If it doesn't, rebuild the container.
2. **Log in as yourself.** In a Codespace there is no local browser, so use:
   ```sh
   gcloud auth application-default login --no-launch-browser
   ```
   Open the printed URL in your own browser, sign in with your work account, and paste the code back. In the local devcontainer, `gcloud auth application-default login` opens the browser for you. The login is stored in your home folder, so a container rebuild means logging in again.
3. **Get access.** Ask a project owner to grant you Token Creator on the development account (the owner runs this once per person):
   ```sh
   gcloud iam service-accounts add-iam-policy-binding DEV_SA_EMAIL --project=PROJECT_ID \
     --role=roles/iam.serviceAccountTokenCreator --member="user:YOU@your-domain"
   ```
4. **Configure.** In a Codespace, the secrets `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` and `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL` (the development account) come from the repository's Codespaces secrets. In the devcontainer, put the same two in `app/.env`. Leave `FEDERATION_AUDIENCE` and `SERVICE_ACCOUNT_KEY` unset.
5. **Check it works.** Start the bot (`make dev`) and run any Google-backed command. The boot summary shows `tenant.service_account_email` set and no `tenant.service_account_key`. A `google_token_refused` line names the cause: see Troubleshooting.

**What does not work locally.** Meetings: the development account has no delegation entry, so retro invitations and Meet links fail with `unauthorized_client`. Use the tests' fakes for that code.

**When someone leaves the team.** Remove their grant:
```sh
gcloud iam service-accounts remove-iam-policy-binding DEV_SA_EMAIL --project=PROJECT_ID \
  --role=roles/iam.serviceAccountTokenCreator --member="user:THEM@your-domain"
```
Every impersonation is recorded when Data Access audit logs are on for the IAM Service Account Credentials API (IAM & Admin > Audit Logs).

On another platform (Azure, Kubernetes, OpenShift), generate a credential configuration file with `gcloud iam workload-identity-pools create-cred-config` for that platform's provider and point `GOOGLE_APPLICATION_CREDENTIALS` at it. The file holds no key. Set `SERVICE_ACCOUNT_EMAIL`, and leave the audience and the key unset.

## 9. Verify

1. Deploy, then run `zsh bin/deploy-checks.zsh post google`. It must show Google configured on every task, the credential source each task uses, and no refused token. After setting the federation audience, run `zsh bin/deploy-checks.zsh post google:federation`, which also requires federation on every task.
2. In Slack, declare a test incident. It should create the folder, the document and a Meet link. Then close it.
3. Schedule a test retro. The invitation should arrive from the bot user.

## Troubleshooting

Boot failures name the variable:

| Boot message | Fix |
| --- | --- |
| `CUSTOMER_ID is set without a credential` | Set the audience with the email (ECS), the email alone (local), or the key (until TASK-182) |
| `FEDERATION_AUDIENCE is set but SERVICE_ACCOUNT_EMAIL is not` | Set the service-account email |
| `FEDERATION_AUDIENCE is not a workload identity provider audience` | Copy the audience from step 3: project number, pool and provider ids of 4 to 32 characters. The terraform placeholder also fails here |
| `FEDERATION_AUDIENCE is set but no AWS region is configured` | Set `AWS_REGION` |
| `SERVICE_ACCOUNT_EMAIL does not name the account of SERVICE_ACCOUNT_KEY` | The email and the key belong to different accounts; fix the email |

At run time, the `google_token_refused` log line carries a `cause`:

| Cause | Usual reason |
| --- | --- |
| `invalid_grant` | STS refused the AWS credential (the provider's condition does not match the task role or account), or a key was revoked |
| `permission_denied` | The Token Creator or Workload Identity User grant is missing for this caller (step 3, or step 3 of the local section) |
| `unauthorized_client` | The delegation entry (step 7) lacks the client id or the scope, or the account has no delegation (local) |
| `aws_credentials_unavailable` | The task has no task role, or the ECS credentials endpoint failed |
| `application_default_credentials_unavailable` | No `gcloud auth application-default login` in this container, or `GOOGLE_APPLICATION_CREDENTIALS` points nowhere |

Google's own messages, as the Google Cloud console's logs show them:

| Message | Usual cause |
| --- | --- |
| `The given credential is rejected by the attribute condition` | The task role name or AWS account in step 3 doesn't match the running task |
| `Permission 'iam.serviceAccounts.getAccessToken' denied` | The step 3 grants are missing, or name another role |
| `unauthorized_client` when scheduling a meeting | The client ID or scopes in step 7 are wrong, or not yet applied |
| `Service accounts cannot invite attendees without Domain-Wide Delegation of Authority` | `DELEGATED_USER_EMAIL` is unset, or step 7 is missing |
| `403 Not Authorized to access this resource/api` on a directory call | The step 5 role isn't assigned to the service account |
| `404 File not found` on a document or folder | The service account isn't a member of the shared drive (step 6), or the file lives in someone's My Drive |

## Until the transition ends

The bot supports every keyless path described above. CDS production still differs from the target until these tasks land:

- TASK-180.1: production cuts over from the JSON key to federation (the audience parameter).
- TASK-185: Codespaces use the development account instead of the production key.
- TASK-182: the key is deleted.
- TASK-181: only meetings delegate. Until then every call delegates to the bot user, so a new deployment needs delegation scopes for every API in the [README table](../../app/integrations/google_workspace/README.md#service-identity).
- TASK-183: the delegation entry keeps only the three meetings scopes, and the bot user loses its admin role.

This section is deleted when TASK-183 is Done.
