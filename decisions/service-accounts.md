---
status: Accepted
date: 2026-08-05
applies: target
scope: When a feature needs a dedicated non-human identity inside a third-party SaaS, how that identity relates to the org IDP and the Directory port, whom the bot acts as, and how it authenticates without stored keys.
---

# SaaS Service Accounts

## Context

Some outbound features don't just *call* a SaaS — they *mutate* it (Slack usergroup membership, a ticketing system's assignments, a repo's teams). A subset of those mutations are gated by the vendor's own authorization model behind **human/administrative authority**, not merely behind a scope a machine credential can hold. Slack is the live example: with *"who can create/edit user groups"* set to Admins/Owners, `usergroups.create` / `usergroups.enable` / `usergroups.users.update` reject a bot token (`xoxb-`) regardless of scopes; only a **user token** (`xoxp-`) minted by an admin/owner works ([Slack token types](https://docs.slack.dev/authentication/tokens/) — bot tokens are app-bound and survive user deactivation; user tokens act *as the person* and carry that person's permissions). `oncall_sync` hit exactly this: its adapter reuses the shared inbound **bot** token (`SlackClientManager.get_client()`), which can never satisfy the admin gate.

The naive unblock — reuse a real employee's personal admin account to mint the token — couples the integration's lifecycle to that human (offboarding/deactivation silently breaks it), muddies audit attribution (the vendor stamps `created_by`/`updated_by` with the authorizing user), and widens blast radius (a personal admin token). This record decides when to provision a **dedicated non-human identity** instead, and how that identity stays decoupled from the organization's IDP.

## Decision

**When the vendor's authz model forces a principal the shared app/bot credential can't be, provision a dedicated SaaS-local service identity — never a personal account, never the shared inbound credential.**

1. **Segregated, least-privilege credential.** The privileged credential is distinct from the transport's inbound credential and from any read-only credential — one credential per role (OWASP API5:2023 BFLA; 12-factor IV "attached resources"). It is owned by `app/integrations/<vendor>/settings.py`, resolved through a provider, and consumed **only** inside the `adapters/<vendor>.py` of the feature or capability that needs it ([plugin-architecture.md](plugin-architecture.md)) — per [platform-transports.md](platform-transports.md) role 3 and [outbound-clients.md](outbound-clients.md). It is a secret: resolved via `SecretsService`/deploy-time injection, never a plaintext default, never logged, rotated by redeploy ([configuration.md](configuration.md), [cloud-portability.md](cloud-portability.md), [observability.md](observability.md)).

2. **Prefer the least-human credential the vendor allows.** Use an app/OAuth-app/machine credential when the operation permits it; fall back to a dedicated service *user* only when the vendor gates the operation behind a human principal (the Slack usergroup admin gate). A service *user* is still non-human in ownership — a dedicated identity, not a real employee's account — so its lifecycle is owned by the platform team, not by HR offboarding.

3. **Provisioning is per-SaaS and case-by-case.** No two SaaS share an identity model, scope taxonomy, or admin-gating rule, so there is **no universal recipe** and none is attempted here. Each SaaS that needs a service identity documents its own "service identity" section (identity, credential type, scopes, owner, rotation) in the owning feature/vendor README, next to the adapter, and its admin steps in a runbook under `docs/runbooks/` that the section links to ([governance.md](governance.md)) — not in this record ([governance.md](governance.md) "why vs how").

4. **The service account is a driven-adapter concern, decoupled from the IDP and the Directory port (hexagonal).** Three actors must not be conflated:
   - the **organization's IDP** (Google Workspace *in this deployment*; could be Entra ID/Okta) — the source of human/machine identities. The app must not assume which one ([cloud-portability.md](cloud-portability.md): env-selected providers, IDP-neutral ports);
   - the **`Directory`** port — the app's IDP-neutral "who is a person here" Protocol, exposed by the people capability's `api.py` in `capabilities/` (today `app/infrastructure/directory/`);
   - the **SaaS-local service identity** — a non-human principal that exists *inside the vendor* to hold the credential the vendor's authz model demands.

   These are different positions on the hexagon: `Directory` is a driven port the app reads; the SaaS service identity is a provisioning property of a *specific driven adapter*. Where a service *user* needs a login/mailbox to exist, that is supplied by whatever IDP the deployment runs — the app depends on the *capability* ("an identity that can authenticate to this SaaS"), never on Google Workspace specifically. An IDP move re-homes the identity's login; it does not touch the adapter's contract, and each SaaS service account stays its own vendor-scoped artifact.

5. **The bot acts as itself, keyless where the vendor federates, and as a user only where the vendor demands one.**
   - **Never as the requesting person.** A change made for someone in chat is made by the bot's own identity; who asked is named in the content and recorded in the app's records and audit ([workplace-systems.md](workplace-systems.md) rule 5), never by impersonating that person. Impersonating each requester would need a grant over every account in the domain, fails for people who work only in another suite, and turns a chat address into an identity ([people-and-accounts.md](people-and-accounts.md)). Dispatch, the closest open-source peer, also delegates to one fixed account ("Outgoing emails and other artifacts will appear to be from this account": [Dispatch Google configuration](https://github.com/Netflix/dispatch/blob/master/src/dispatch/plugins/dispatch_google/config.py)).
   - **No stored key where the vendor accepts the platform's workload identity.** The credential is a short-lived token minted from the compute platform's own identity (the ECS task role), as [cloud-portability.md](cloud-portability.md) rule 1 prefers. A stored key is tolerated only until the federated path is live, then deleted.
   - **A user identity only for an operation the vendor refuses to a machine principal**, held by the dedicated service user of rule 2, with only that operation's scopes.
   - **One machine identity may hold several roles when they run in the same workload.** Separate accounts would not separate who holds them; each call's token carries only that call's scopes, which is the credential per role rule 1 asks for here.

   **Google Workspace** (sources read on 2026-11-04):

   | Role | Principal | Scopes on the token |
   | --- | --- | --- |
   | People directory read | The service account itself, holding an assigned admin role (Users read, Groups read) | `admin.directory.*.readonly` per call |
   | Group membership write | The same, the role also allowing group updates | `admin.directory.group.member` |
   | Incident and talent documents, folders and sheets | The service account itself, Content manager of the shared drive that holds them | `drive`, `documents`, `spreadsheets`, reaching only what the drive shares |
   | Meetings: Calendar events with attendees, Meet spaces | Domain-wide delegation to the dedicated bot user, the meetings' organiser | `calendar.events`, `calendar.freebusy`, `meetings.space.created`: the only scopes on the delegation entry |

   - Why each row: any admin role except Super Admin can be assigned to a service account ([create credentials](https://developers.google.com/workspace/guides/create-credentials)); a service account has no storage quota and works in shared drives ([shared drives](https://developers.google.com/workspace/drive/api/guides/about-shareddrives)); Calendar needs delegation "to populate the attendee list" ([events](https://developers.google.com/workspace/calendar/api/v3/reference/events)); Meet accepts user authentication only ([Meet auth](https://developers.google.com/workspace/meet/api/guides/authenticate-authorize)). Delegation cannot be limited to particular users and can reach super admins ([delegation](https://knowledge.workspace.google.com/admin/apps/control-api-access-with-domain-wide-delegation), [service-account best practices](https://docs.cloud.google.com/iam/docs/best-practices-service-accounts)), so every scope on the entry is a standing power over every account in the domain.
   - Authentication: Workload Identity Federation from the ECS task role to the service account, through a boto3-backed `AwsSecurityCredentialsSupplier`, because google-auth's built-in AWS source reads only EC2 metadata or environment variables and Fargate has no instance profile ([auth libraries](https://docs.cloud.google.com/iam/docs/authenticate-with-auth-libraries), [ECS task roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)). Delegation uses signJwt, not a key ("Using service account keys is not necessary to perform domain-wide delegation": [delegation best practices](https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices)). The federation pool's condition pins the AWS account and the task role ([WIF best practices](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation)). That supplier is the ECS adapter only. Every other platform uses application default credentials: a developer's gcloud login, a GCP runtime, or a Workload Identity Federation credential configuration file (Azure managed identity, a Kubernetes or OpenShift token file, an executable), which holds no key and is loaded through `GOOGLE_APPLICATION_CREDENTIALS` with no code change ([WIF with other clouds](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds)). Both then impersonate the service account in the gateway, so delegation keeps its subject. AWS outbound identity federation (STS `GetWebIdentityToken`, [AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)) would make AWS a generic OIDC issuer. It is not used: it needs an account-level opt-in and still a boto3 call, and gains nothing over Google's AWS provider.
   - Developers: a developer authenticates with their own gcloud login and a revocable Token Creator grant, never a copied key ([local ADC](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)). The grant is on a development service account in its own project, without a delegation entry and holding only a test shared drive. It is bound to a Workspace group, not to people, so joining and leaving the team are group membership. Developers hold no project role beyond, if Google requires one for quota, Service Usage Consumer on that development project, and Google Cloud is turned on in the Admin console for that group only. It is never on the production account, where Token Creator would let a laptop mint delegated tokens for any user the entry covers. Running against Google locally is optional: without a tenant entry the bot runs without Google, and tests use fakes. GitHub Codespaces issue no OIDC token, so a Codespace cannot federate.
   - No cost: all IAM API use is free ([IAM pricing](https://cloud.google.com/iam/pricing)), which covers pools, providers, service accounts, generateAccessToken and signJwt; the Workspace APIs used are no-cost within quota.
   - The organisation's GCP project hosts the account: a dedicated project is not required, and project-wide organisation policies are not set where the project hosts other teams' accounts; key creation on the bot's account is limited through IAM. The steps live in the service identity section of `integrations/google_workspace/README.md` (rule 3).

## Consequences

- Some SaaS mutations cannot run on a machine credential at all: a provisioned identity is a **manual, vendor-specific, often admin-approval prerequisite** outside the repo, and the feature stays blocked until it exists. That is inherent to the vendor's model, not a code defect.
- Not every SaaS needs this — read-only or machine-scoped operations use ordinary app/bot credentials and add no identity to manage.
- A Google resource the bot changes shows the bot as its editor, never the person who asked in chat; attribution lives in the content and the app's records.
- Google meetings stay the one delegated use, so the bot's Workspace user remains a licensed account to own, with no admin role.
- Cost: each vendor that needs one adds an identity to own (lifecycle, least-privilege scoping, rotation, audit). We accept it to avoid coupling an integration to a human account. Note a service *user*'s token is human-shaped, so it rotates on suspicion/role-change rather than on a fixed machine-secret schedule ([NIST 800-63](https://pages.nist.gov/800-63-FAQ/#q-b05)); document its rotation trigger explicitly.

## Checks

- grep/review: no feature adapter performing a privileged SaaS write reuses the shared inbound/bot credential (each such write takes a role-segregated credential from the vendor's settings slice); no personal-account credential is wired as a feature credential.
- Each SaaS requiring a service identity has a "service identity" section (identity, credential type, scopes, owner, rotation) in its feature/vendor README; its token resolves as a secret (no plaintext default, absent from logs/repr).
- import boundary holds: the privileged credential is constructed in the provider/`integrations/` layer and used only inside a feature's or capability's `adapters/`, never in service/domain code.
- Tests: only the Google Calendar and Meet factories apply a delegation subject; no caller passes a subject.
- Review: no Google service-account key in configuration, SSM or a Codespaces secret; the Google delegation entry lists only the meetings scopes, and the bot's Workspace user holds no admin role (Admin console, against the README).

## Migration

Tickets: TASK-71 (closed: `oncall_sync` writes user groups with its own `SLACK__USER_TOKEN`); for Google, TASK-180 (Workload Identity Federation to the existing service account; production stays on the key), TASK-180.1 (the cutover: the federation audience parameter), TASK-185 (the development service account), TASK-181 (only Calendar and Meet delegate; scopes narrowed), TASK-182 (the key deleted) and TASK-183 (the delegation entry reduced to the meetings scopes; the bot user's admin role removed). `applies` stays `target` until the Checks are confirmed on `main`.

Tolerated until then:
- the Google JSON key in SSM and a Codespaces secret (TASK-182);
- every Google call delegating to the bot's Workspace user, and the `calendar` scope (TASK-181);
- delegation entry scopes beyond the meetings scopes, and an admin role on the bot's Workspace user (TASK-183).

**Changes:**
- 2026-09-24: Migration records that TASK-71 closed the `oncall_sync` shared-token divergence; privileged credentials are used only in a feature's or capability's `adapters/`.
- 2026-11-05: rule 5: the bot acts as itself, never as the requesting person; keyless federation where the vendor accepts the platform identity; a user identity only for operations the vendor refuses to a machine principal; one machine identity may hold the roles of one workload. Google applies it: directory and documents as the service account, delegation only for meetings (TASK-169, human). Rule 3's admin steps move to a linked runbook, as governance.md puts procedures in `docs/runbooks/`.
- 2026-11-05: rule 5: the AWS supplier is the ECS adapter, and application default credentials, including credential configuration files, are the platform default. Developers impersonate a development service account, never the production one. No key is kept as a fallback: until TASK-182 the key path is the cutover's rollback, and afterwards recovery means fixing the federation configuration (TASK-180 planning, human).
- 2026-11-05: developers with Workspace access only reach the development account through a group-bound Token Creator grant on the account, in a dedicated project, with Google Cloud turned on for that group only; local Google is optional (TASK-185 scope, human).
