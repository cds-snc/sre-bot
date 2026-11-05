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

1. Create the pool and the AWS provider. The condition admits only your task role:
   ```sh
   gcloud iam workload-identity-pools create sre-bot --location=global --project=PROJECT_ID \
     --display-name="SRE Bot (AWS)"
   gcloud iam workload-identity-pools providers create-aws aws --location=global \
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
   `//iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/sre-bot/providers/aws`.

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

To run the bot locally, use your own Google login instead of a key:

1. Run `gcloud auth application-default login`.
2. Have a project owner grant you `roles/iam.serviceAccountTokenCreator` on `SA_EMAIL`. Remove the grant when you leave the team.
3. Leave the federation audience unset.

## 9. Verify

1. Deploy, then run `bin/deploy-checks.zsh post google`. It must show Google configured on every task and no credential or delegation error.
2. In Slack, declare a test incident. It should create the folder, the document and a Meet link. Then close it.
3. Schedule a test retro. The invitation should arrive from the bot user.

## Troubleshooting

| Message | Usual cause |
| --- | --- |
| `The given credential is rejected by the attribute condition` | The task role name or AWS account in step 3 doesn't match the running task |
| `Permission 'iam.serviceAccounts.getAccessToken' denied` | The step 3 grants are missing, or name another role |
| `unauthorized_client` when scheduling a meeting | The client ID or scopes in step 7 are wrong, or not yet applied |
| `Service accounts cannot invite attendees without Domain-Wide Delegation of Authority` | `DELEGATED_USER_EMAIL` is unset, or step 7 is missing |
| `403 Not Authorized to access this resource/api` on a directory call | The step 5 role isn't assigned to the service account |
| `404 File not found` on a document or folder | The service account isn't a member of the shared drive (step 6), or the file lives in someone's My Drive |

## Until TASK-180 ships

The released bot authenticates with a JSON key (`GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY`) and delegates every call to the bot user. Until TASK-180, 181 and 183 land, a new deployment needs both, and delegation scopes for every API in the [README table](../../app/integrations/google_workspace/README.md#service-identity). This section is deleted when TASK-183 is Done.
