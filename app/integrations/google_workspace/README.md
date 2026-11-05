# Google Workspace integration

The one gateway to Google Workspace ([decisions/workplace-systems.md](../../../decisions/workplace-systems.md)). Like every vendor package ([decisions/outbound-clients.md](../../../decisions/outbound-clients.md)), it exports three things:

- `client.py`: authenticated service factories (Directory, Calendar, Meet, Docs, Drive, Sheets), each with an explicit per-attempt timeout and a small retry default;
- `classify_google_error`, the error classifier the adapters use;
- `settings.py`: the `[google_workspace]` slice and the tenant entry, which chooses the credential source at boot.

`client.py` also builds the three credential sources (AWS federation, application default credentials, the key) once per tenant, on the first call. The credentials, and which calls delegate to a user, are decided inside client construction. Callers pass the scopes their call needs and nothing else.

Features and capabilities reach Google only from their own `adapters/`, through ports named for their purpose (the people directory, an incident's documents). There is no Drive, Sheets or Calendar capability.

## Service identity

Required by [decisions/service-accounts.md](../../../decisions/service-accounts.md) rule 3. Rule 5 says why the bot acts as itself and delegates only for meetings.

**Identity.**
- One GCP service account in the organisation's project (CDS: `cdssnc`). It acts as itself for everything except meetings.
- One dedicated Workspace user, the bot user, is the organiser of meetings. Domain-wide delegation to it is used only for Calendar events with attendees and Meet spaces.
- The bot never acts as the person who asked in chat. That person is named in the content and recorded in the app.

| Role | Principal | Scopes |
| --- | --- | --- |
| People directory read (users, groups, members) | The service account, holding an assigned admin role: Users read, Groups read | `admin.directory.customer.readonly`, `admin.directory.user.readonly`, `admin.directory.group.readonly`, `admin.directory.group.member.readonly`, each per call |
| Group membership write (access requests) | The service account; the same admin role also allows group updates | `admin.directory.group.member` |
| Incident documents, folders and list sheet; talent role folders; AWS spending sheet | The service account, Content manager of the shared drive that holds them | `drive`, `documents`, `spreadsheets`: they reach only what that drive shares with the account |
| Meetings: retro and postmortem events with invitations, incident Meet spaces | Delegation to the bot user | `calendar.events`, `calendar.freebusy`, `meetings.space.created`: the **only** scopes on the delegation entry |

**Credentials at a glance.** The bot always ends up acting as a service account. What differs is how it proves who it is:

| Where the bot runs | How it proves its identity | What you set | Who grants access |
| --- | --- | --- | --- |
| ECS (production) | AWS federation: the task role's credentials are exchanged at Google STS, then the service account is impersonated | `CUSTOMER_ID`, `SERVICE_ACCOUNT_EMAIL`, `FEDERATION_AUDIENCE` | The pool's condition admits only the task role `sre-bot-ecs-role` |
| A Codespace or the devcontainer | Your own Google login (`gcloud auth application-default login`), then impersonation of the development service account | `CUSTOMER_ID`, `SERVICE_ACCOUNT_EMAIL` | A project owner gives you Token Creator on that account (TASK-185) |
| Another platform (Azure, Kubernetes, OpenShift, GCP) | A Workload Identity Federation credential configuration file read by Google's library, then impersonation | `CUSTOMER_ID`, `SERVICE_ACCOUNT_EMAIL`, and `GOOGLE_APPLICATION_CREDENTIALS` pointing at the file | The pool's provider for that platform |
| Production until TASK-182 | The JSON key | `CUSTOMER_ID`, `SERVICE_ACCOUNT_KEY` (and `SERVICE_ACCOUNT_EMAIL`, which must be the key's account) | Whoever holds the key: this is why it is being deleted |

Every name above is `GOOGLE_WORKSPACE__TENANT__<NAME>`, except `GOOGLE_APPLICATION_CREDENTIALS`. Meetings delegate to the bot user through IAM signJwt on the keyless paths, so no key is needed for delegation either.

**How the bot chooses.** At boot, with no network call, the first match wins:
1. `FEDERATION_AUDIENCE` set: AWS federation. It needs `SERVICE_ACCOUNT_EMAIL` and an AWS region (`AWS_REGION`), and the audience must look like `//iam.googleapis.com/projects/<project number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>`.
2. `SERVICE_ACCOUNT_KEY` set: the key. A set `SERVICE_ACCOUNT_EMAIL` must be the key's own account.
3. `SERVICE_ACCOUNT_EMAIL` alone: application default credentials, resolved on the first Google call.
4. `CUSTOMER_ID` with none of them: boot fails naming the three options. No `CUSTOMER_ID` and nothing else set: Google is simply not configured, and the bot runs without it.

When a Google call is refused, the log line `google_token_refused` gives the cause (for example `permission_denied`, `invalid_grant`, `application_default_credentials_unavailable`). The runbook's troubleshooting table says what each means.

**Configuration.** Every value comes from the environment, and none goes in a configuration file ([decisions/configuration.md](../../../decisions/configuration.md)):

| Variable | Class |
| --- | --- |
| `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` | non-public |
| `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL` | non-public |
| `GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE` | non-public; set only on ECS |
| `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY` | secret; until TASK-182 |
| `GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL` | non-public; the meetings organiser, optional when meetings are not used |

**Owner.** The SRE team: the GCP project IAM, the Admin console role assignment, the shared-drive membership and the delegation entry.

**Rotation.**
- Federation and impersonated tokens last an hour and refresh on their own, so there is no key to rotate.
- A developer's access is their own Token Creator grant: remove it when they leave the team.
- Revoke access by removing the provider's IAM grants, or by disabling the service account.
- The bot user is a human-shaped account: change its password and sessions on suspicion or when its owners change.
- Review the delegation entry against the table above whenever a Google call is added.

### Transition

Until these tasks land, production differs from the target:

| Task | Change |
| --- | --- |
| TASK-180 | the keyless sources ship; production stays on the key |
| TASK-180.1 | production cuts over to federation (the audience parameter) |
| TASK-185 | Codespaces use a development service account instead of the production key |
| TASK-182 | the key is deleted |
| TASK-181 | only meetings delegate; `calendar` is narrowed to `calendar.events` and `calendar.freebusy` |
| TASK-183 | the delegation entry is reduced to the three meetings scopes, and the bot user loses its admin role |

Today, production authenticates with the JSON key and every call delegates to the bot user.

### Setup

The steps for a new organisation, or to rebuild this one's access, are in [docs/runbooks/set-up-google-workspace-access.md](../../../docs/runbooks/set-up-google-workspace-access.md). It covers the four Google pieces explained plainly, the GCP and Admin console steps, the configuration, running the bot locally, verification and troubleshooting. CDS uses the `cdssnc` project, the task role `sre-bot-ecs-role`, the pool `sre-bot` and the provider `aws-ecs`.

### Sources

Read on 2026-11-04 and 2026-11-05:
- [Workload Identity Federation with other clouds](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds)
- [custom AWS credential supplier](https://docs.cloud.google.com/iam/docs/authenticate-with-auth-libraries)
- [delegation best practices](https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices)
- [admin roles for service accounts](https://developers.google.com/workspace/guides/create-credentials)
- [Calendar attendees need delegation](https://developers.google.com/workspace/calendar/api/v3/reference/events)
- [Meet requires user authentication](https://developers.google.com/workspace/meet/api/guides/authenticate-authorize)
- [IAM pricing](https://cloud.google.com/iam/pricing)
- [Set up ADC for local development](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)
- [gcloud create-aws: provider ids are 4 to 32 characters](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/providers/create-aws)
