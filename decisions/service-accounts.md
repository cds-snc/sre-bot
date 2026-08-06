---
status: Accepted
date: 2026-08-05
applies: target
scope: When a feature needs a dedicated non-human identity inside a third-party SaaS, and how that identity relates to the org IDP and the Directory port.
---

# SaaS Service Accounts

## Context

Some outbound features don't just *call* a SaaS — they *mutate* it (Slack usergroup membership, a ticketing system's assignments, a repo's teams). A subset of those mutations are gated by the vendor's own authorization model behind **human/administrative authority**, not merely behind a scope a machine credential can hold. Slack is the live example: with *"who can create/edit user groups"* set to Admins/Owners, `usergroups.create` / `usergroups.enable` / `usergroups.users.update` reject a bot token (`xoxb-`) regardless of scopes; only a **user token** (`xoxp-`) minted by an admin/owner works ([Slack token types](https://docs.slack.dev/authentication/tokens/) — bot tokens are app-bound and survive user deactivation; user tokens act *as the person* and carry that person's permissions). `oncall_sync` hit exactly this: its adapter reuses the shared inbound **bot** token (`SlackClientManager.get_client()`), which can never satisfy the admin gate.

The naive unblock — reuse a real employee's personal admin account to mint the token — couples the integration's lifecycle to that human (offboarding/deactivation silently breaks it), muddies audit attribution (the vendor stamps `created_by`/`updated_by` with the authorizing user), and widens blast radius (a personal admin token). This record decides when to provision a **dedicated non-human identity** instead, and how that identity stays decoupled from the organization's IDP.

## Decision

**When the vendor's authz model forces a principal the shared app/bot credential can't be, provision a dedicated SaaS-local service identity — never a personal account, never the shared inbound credential.**

1. **Segregated, least-privilege credential.** The privileged credential is distinct from the transport's inbound credential and from any read-only credential — one credential per role (OWASP API5:2023 BFLA; 12-factor IV "attached resources"). It is owned by `app/integrations/<vendor>/settings.py`, resolved through a provider, and consumed **only** inside the feature's `adapters/<vendor>.py` (Path B) or a Path A capability implementation — per [platform-transports.md](platform-transports.md) role 3 and [outbound-clients.md](outbound-clients.md). It is a secret: resolved via `SecretsService`/deploy-time injection, never a plaintext default, never logged, rotated by redeploy ([configuration.md](configuration.md), [cloud-portability.md](cloud-portability.md), [observability.md](observability.md)).

2. **Prefer the least-human credential the vendor allows.** Use an app/OAuth-app/machine credential when the operation permits it; fall back to a dedicated service *user* only when the vendor gates the operation behind a human principal (the Slack usergroup admin gate). A service *user* is still non-human in ownership — a dedicated identity, not a real employee's account — so its lifecycle is owned by the platform team, not by HR offboarding.

3. **Provisioning is per-SaaS and case-by-case.** No two SaaS share an identity model, scope taxonomy, or admin-gating rule, so there is **no universal recipe** and none is attempted here. Each SaaS that needs a service identity documents its own "service identity" section (identity, credential type, scopes, admin steps, owner, rotation) in the owning feature/vendor README, next to the adapter — not in this record ([governance.md](governance.md) "why vs how").

4. **The service account is a driven-adapter concern, decoupled from the IDP and the Directory port (hexagonal).** Three actors must not be conflated:
   - the **organization's IDP** (Google Workspace *in this deployment*; could be Entra ID/Okta) — the source of human/machine identities. The app must not assume which one ([cloud-portability.md](cloud-portability.md): env-selected providers, IDP-neutral ports);
   - the core **`Directory`** capability — the app's IDP-neutral "who is a person here" Path A port;
   - the **SaaS-local service identity** — a non-human principal that exists *inside the vendor* to hold the credential the vendor's authz model demands.

   These are different positions on the hexagon: `Directory` is a driven port the app reads; the SaaS service identity is a provisioning property of a *specific driven adapter*. Where a service *user* needs a login/mailbox to exist, that is supplied by whatever IDP the deployment runs — the app depends on the *capability* ("an identity that can authenticate to this SaaS"), never on Google Workspace specifically. An IDP move re-homes the identity's login; it does not touch the adapter's contract, and each SaaS service account stays its own vendor-scoped artifact.

## Consequences

- Some SaaS mutations cannot run on a machine credential at all: a provisioned identity is a **manual, vendor-specific, often admin-approval prerequisite** outside the repo, and the feature stays blocked until it exists. That is inherent to the vendor's model, not a code defect.
- Not every SaaS needs this — read-only or machine-scoped operations use ordinary app/bot credentials and add no identity to manage.
- Cost: each vendor that needs one adds an identity to own (lifecycle, least-privilege scoping, rotation, audit). We accept it to avoid coupling an integration to a human account. Note a service *user*'s token is human-shaped, so it rotates on suspicion/role-change rather than on a fixed machine-secret schedule ([NIST 800-63](https://pages.nist.gov/800-63-FAQ/#q-b05)); document its rotation trigger explicitly.

## Checks

- grep/review: no feature adapter performing a privileged SaaS write reuses the shared inbound/bot credential (each such write takes a role-segregated credential from the vendor's settings slice); no personal-account credential is wired as a feature credential.
- Each SaaS requiring a service identity has a "service identity" section (identity, credential type, scopes, owner, rotation) in its feature/vendor README; its token resolves as a secret (no plaintext default, absent from logs/repr).
- import boundary holds: the privileged credential is constructed in the provider/`integrations/` layer and used only inside `packages/<feature>/adapters/` (or a Path A impl), never in service/domain code.

## Migration

Ticket: TASK-71 — `oncall_sync` admin-scoped Slack credential (add a `SLACK_ONCALL_ADMIN_TOKEN` field to the Slack integration settings slice; build a separate admin-scoped Web client; rewire `get_user_group_sync_target()` in `app/packages/oncall_sync/providers.py` to use it behind `UserGroupSyncTarget`; document the Slack service-identity provisioning in the feature README). Tolerated until closed: `oncall_sync` reusing the shared inbound bot token for usergroup writes — the current cause of its `permission_denied` failures.
