# Google Workspace integration

The one gateway to Google Workspace ([decisions/workplace-systems.md](../../../decisions/workplace-systems.md)). Like every vendor package ([decisions/outbound-clients.md](../../../decisions/outbound-clients.md)), it exports three things:

- `client.py`: authenticated service factories (Directory, Calendar, Meet, Docs, Drive, Sheets), each with an explicit per-attempt timeout and a small retry default;
- `classify_google_error`, the error classifier the adapters use;
- `settings.py`: the `[google_workspace]` slice and the tenant entry.

The credentials, and which calls delegate to a user, are decided inside client construction. Callers pass the scopes their call needs and nothing else.

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

**Credential type.**
- On ECS: Workload Identity Federation from the task role `sre-bot-ecs-role`. The token is exchanged at Google STS, then the service account is impersonated, giving one-hour tokens.
- Meetings delegate through signJwt. No key is stored.
- A developer uses their own `gcloud auth application-default login` plus a Token Creator grant on the service account, given per person and revoked when they leave.

**Configuration.** Every value comes from the environment, and none goes in a configuration file ([decisions/configuration.md](../../../decisions/configuration.md)):

| Variable | Class |
| --- | --- |
| `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` | non-public |
| `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL` | non-public |
| `GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE` | |
| `GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL` | non-public; the meetings organiser, optional when meetings are not used |

**Owner.** The SRE team: the GCP project IAM, the Admin console role assignment, the shared-drive membership and the delegation entry.

**Rotation.**
- Federation tokens expire and refresh on their own, so there is no key to rotate.
- Revoke access by removing the provider's IAM grants, or by disabling the service account.
- The bot user is a human-shaped account: change its password and sessions on suspicion or when its owners change.
- Review the delegation entry against the table above whenever a Google call is added.

### Transition

Until these tasks land, production differs from the target:

| Task | Change |
| --- | --- |
| TASK-180 | federation replaces the key |
| TASK-182 | the key is deleted |
| TASK-181 | only meetings delegate; `calendar` is narrowed to `calendar.events` and `calendar.freebusy` |
| TASK-183 | the delegation entry is reduced to the three meetings scopes, and the bot user loses its admin role |

Today, every call delegates to the bot user with a JSON key.

### Setup

The steps for a new organisation, or to rebuild this one's access, are in [docs/runbooks/set-up-google-workspace-access.md](../../../docs/runbooks/set-up-google-workspace-access.md). That covers the four Google pieces explained plainly, the GCP and Admin console steps, the configuration, verification and troubleshooting. CDS uses the `cdssnc` project and the task role `sre-bot-ecs-role`.

### Sources

Read on 2026-11-04:
- [Workload Identity Federation with other clouds](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds)
- [custom AWS credential supplier](https://docs.cloud.google.com/iam/docs/authenticate-with-auth-libraries)
- [delegation best practices](https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices)
- [admin roles for service accounts](https://developers.google.com/workspace/guides/create-credentials)
- [Calendar attendees need delegation](https://developers.google.com/workspace/calendar/api/v3/reference/events)
- [Meet requires user authentication](https://developers.google.com/workspace/meet/api/guides/authenticate-authorize)
- [IAM pricing](https://cloud.google.com/iam/pricing)
