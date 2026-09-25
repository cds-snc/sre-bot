---
status: Accepted
date: 2026-09-25
applies: target
scope: How the app identifies people across identity providers and chat platforms: person records, linked identities and accounts, how callers are resolved, storage, and where a conversation is handled.
---

# People and Accounts

## Context

Every way into the bot is federated to the organization's identity provider (IdP): Slack enforces SSO against it, and Backstage signs users in through it, with the bot validating Backstage's tokens against JWKS ([security.md](security.md)). The IdP is Google today; it may become Microsoft Entra ID, or both may run in parallel. Teams will join Slack ([workplace-systems.md](workplace-systems.md)). Google and Microsoft addresses for the same person differ, and naming patterns aren't enforced. Who counts as a contractor is an open organization-level question. Partners are out of scope.

Addresses are not identities. OIDC keys only on issuer plus subject ([OIDC Core §5.7](https://openid.net/specs/openid-connect-core-1_0.html)). Google advises against keying persistent data on email ([Directory API](https://developers.google.com/workspace/admin/directory/v1/guides/manage-users)). In Entra, `oid` plus `tid` is the stable key; `sub` is pairwise per app, and email and UPN can be reassigned ([ID token claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference)). Multi-IdP identity systems keep an internal stable id and link external identities to it: SCIM `id` versus `externalId` ([RFC 7643 §3.1](https://datatracker.ietf.org/doc/html/rfc7643#section-3.1)), Keycloak federated identity links ([admin guide](https://www.keycloak.org/docs/latest/server_admin/index.html)), Okta's single user object ([Universal Directory](https://developer.okta.com/docs/concepts/universal-directory/)). Auth0 instead keys users on the primary IdP's id ([account linking](https://auth0.com/docs/manage-users/user-accounts/user-account-linking)), which ties the key to one IdP. Linking identities automatically by email is a known account-takeover path ([Auth0](https://auth0.com/docs/manage-users/user-accounts/user-account-linking/link-user-accounts), [CVE-2025-7365](https://advisories.gitlab.com/pkg/maven/org.keycloak/keycloak-services/CVE-2025-7365/)).

What each entry point receives:
- **Slack:** a workspace-scoped user id. The IdP subject isn't exposed to bots; the email that SSO set is, with `users:read.email` ([users.lookupByEmail](https://docs.slack.dev/reference/methods/users.lookupByEmail)). Guests may sign in without SSO, so a guest's email isn't IdP-asserted.
- **Teams:** `aadObjectId`, which is the Entra `oid`, plus `tenantId` ([proactive messages](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages)).
- **Backstage:** `sub` is a catalog entity ref (`user:default/jane`), not the IdP subject. Email and IdP subject appear only if the sign-in resolver adds them as claims ([identity resolver](https://backstage.io/docs/auth/identity-resolver)).

Current state:
- **No person record, people table or `app/capabilities/people/` exists.** DynamoDB is used through `StorageService` (`infrastructure/storage/`), which has single-item `put_if_not_exists` but no atomic multi-item write.
- **Every human is keyed by email.** Directory lookups use `users().get(userKey=email)`. The Directory user `id` is read into `provider_user_id`, but only `modules/dev/google.py` uses it. `infrastructure/security/current_user.py` identifies Backstage callers by the `email` claim. Access stores `actor_email` and `approver_email` (`packages/access/request/`), the audit table indexes `user_email`, and retro attendees come from Slack profile emails (`modules/incident/schedule_retro.py`).
- **The bot never receives a Google OIDC `sub`.** No Google page says it equals the Directory `id`, so the two are treated as different values.
- **The Slack runtime lives in `integrations/slack/`,** so callers can't yet be resolved at an entry point ([platform-entrypoints.md](platform-entrypoints.md)). Directory access is Google-only; there is no Microsoft Graph client.

Deferred: whether the Backstage resolver adds the IdP subject as a claim or the bot looks up the entity ref in the catalog. The Backstage configuration repository is private and wasn't reachable when this was decided.

## Decision

**The app owns the person record.** A `Person` has a stable, opaque, app-generated id. New records that refer to a human (incident roles, meeting attendees, approvers, audit actors) store that id, never an email, a name, an IdP subject or a platform user id. Features never see which IdP or how many IdPs are behind a person.

**IdPs are the authority for who exists.**

- Configuration names each IdP the instance trusts, as an `(idp, tenant)` pair: a Google Workspace customer or domain, an Entra tenant. There is one today, Google, and the model supports several without change.
- An **identity** is a person's account in an IdP, identified by `(idp, tenant, subject)`:
  - `google`: the Directory user `id`, never the OIDC `sub` or an email;
  - `entra`: the object id `oid` with the tenant id `tid`, never the pairwise `sub`, the UPN or an email.
- A scheduled, read-only import creates a person for each identity it reads from a trusted IdP. People are only ever created from an IdP. The bot never writes to the IdP.
- An identity disabled or deleted at the IdP marks its person inactive. The person and links stay for history, and an email later reused for someone else never resolves to the old person.
- Profile attributes (display name, email, manager) come from the person's primary identity, which is the first one imported unless SRE changes it. Emails, UPNs and names are refreshed attributes used for display and lookup. They are never keys.

**Platform accounts resolve to identities through what the IdP asserted, never through matching.**

- A **platform account** is identified by `(platform, tenant, account_id)`: `slack` user id scoped by `team_id` or enterprise id; `teams` `aadObjectId` with `tenantId`; `backstage` user entity ref. It keeps known id aliases, because a Slack user id changes when a workspace joins an Enterprise org.
- Each link from an account or identity to a person records its provenance:
  - `idp`: the person was created from this identity by the IdP import;
  - `idp_subject`: the platform delivered the IdP subject itself (Teams `aadObjectId`, a Backstage claim or catalog annotation holding the subject). This is an exact link;
  - `sso_email`: the account signs in through SSO against a trusted IdP, so its email was set by the IdP, and it matched exactly one active identity in an allowed domain of that IdP. For Slack this means a full member of an SSO-enforced workspace, never a guest (`is_restricted` or `is_ultra_restricted`). For Backstage it means every caller, because sign-in requires IdP SSO. The link is keyed by the platform account id from then on, and the email is only the evidence recorded for it;
  - `admin`: SRE made the link, with an audit record.
- An `sso_email` link is re-checked on each import. If the platform email and the identity's email diverge, the link is flagged for SRE and the link's use is logged. It is never silently moved to another person.
- A platform without SSO enforcement, or an account outside it such as a Slack guest, never gets an `sso_email` link. It stays unlinked unless SRE links it.
- Accounts may exist unlinked. The entry point passes handlers an unlinked marker for them. An unlinked caller isn't refused: each feature's access policy says whether it serves everyone, only callers resolved to an active person, or only people in named IdP groups (TASK-129).
- Creating or removing a link is audit-logged.

**Several IdPs.** A human with identities in two IdPs starts as two people, one per identity. They become one person only through an explicit join: an SRE action with an audit record, or later a self-service join where the person signs in to both IdPs in one session. A shared email may *suggest* a join for SRE to review; it never makes one.

**No person kind, no permissions on the person.** The person record holds identity and links only. Whether someone is an employee or a contractor is an organization-level concern the app doesn't model. Access to a feature or role comes from membership in IdP groups, evaluated per linked identity, decided in TASK-129.

**Home.** People and accounts is a capability at `app/capabilities/people/` ([plugin-architecture.md](plugin-architecture.md)). Its public surface is `api.py` (the Protocol, `Person`, `Identity` and `Account` types, and a provider function) plus its hookspecs; everything else in it is private. Each IdP is read through a directory adapter behind the capability, per [workplace-systems.md](workplace-systems.md) rule 2.

**Storage.** People, identities, accounts and links live in a dedicated table owned by the people capability, written through the storage contract in `contracts/`. Each identity and each account is claimed by exactly one person: the claim and the link go in one atomic conditional write, so two people can never hold the same identity or account. IdPs and platforms are only read; the people table is the only place the app writes identity data.

**Homes.** A person has a home account per service kind: chat, calendar and mail, files.
- A home defaults to the account the person actually uses; for chat, that is the platform their requests come from.
- SRE can override a home.
- Features ask for "this person's calendar" or "reach this person" and never choose a system themselves.

**Conversation origin.**
- The platform entry point resolves the caller's account to a person through the people capability, and hands handlers the result: a person, or unlinked ([platform-entrypoints.md](platform-entrypoints.md)). A first-seen account on an SSO-enforced platform is resolved and linked on that request, per the rules above.
- A conversation-scoped record, such as an incident, stores its origin as `(platform, tenant, channel_id)` and is handled on that platform.
- Until cross-platform conversations exist, each platform is handled independently. Once they exist, participants on another platform are reached through their chat home.

**Adoption order.** Adoption follows expand, shadow, cut over, contract. People are populated from the IdP before any consumer reads them. A consumer compares person-based results with its current behavior before switching, and it keeps an explicit, logged fallback for unlinked people until SRE removes it.

## Consequences

- Email joins stop, so renamed users, typos and differing Google and Microsoft addresses no longer break resolution.
- Moving from Google to Entra, or adding Entra beside Google, touches the people capability, its directory adapters and entry-point resolution. No feature and no stored reference changes.
- Linking needs almost no manual work in the single-IdP case: people come from the IdP, and accounts link through what the IdP asserted. Manual work is limited to cross-IdP joins, flagged `sso_email` links and accounts outside SSO.
- Until an SRE join, a human with identities in two IdPs appears as two people in audit, approvals and on-call.
- Slack resolution rests on SSO enforcement. If a workspace stops enforcing SSO, its `sso_email` links lose their basis and must be re-reviewed.
- Cost: the storage contract needs a new atomic multi-item write before the people store can be built.
- A wrong link routes messages or access to the wrong human. Provenance, audit logging, atomic claims, deprovisioning on IdP deletion and the no-join-on-email rule are the mitigation.
- Person records are personal data: [observability.md](observability.md) redaction rules and [security.md](security.md) least privilege apply.

## Checks

- Review: new stored models refer to humans by person id, not by email, IdP subject or platform user id.
- Review: no code joins identities or accounts by comparing emails, UPNs or names outside the people capability's `sso_email` rule.
- Tests: claiming an identity or account already claimed by another person fails with a conflict and writes nothing.
- Tests: every stored link carries provenance, and link creation and removal emit audit events.
- Tests: an `sso_email` link is refused when the email matches no active identity, matches more than one, or falls outside the trusted IdP's allowed domains.
- Tests: a Slack guest account (`is_restricted` or `is_ultra_restricted`) is never given an `sso_email` link.
- Tests: two identities from different IdPs with the same email produce two people and one suggested join, never one person.
- grep: the people capability's `api.py` exports no field named `kind` and no role or permission field.

## Migration

Coordinator: TASK-83. Its slices follow the Decision's adoption order (expand, shadow, cut over, contract). Authorization by IdP group is TASK-129.

Tolerated until then:
- no `app/capabilities/people/` package;
- no people table and no person record;
- email-based resolution in legacy modules, in `infrastructure/directory/` lookups and in `infrastructure/security/current_user.py`;
- Backstage callers resolved by `sso_email` until the deferred resolver-claim question is settled;
- `actor_email` sort keys in access request decisions and the `user_email` audit index;
- existing records that refer to humans by email or Slack id.

**Changes:**
- 2026-09-24: Migration names epic tickets only, and the capability's home is `app/capabilities/people/` per plugin-architecture.md.
- 2026-09-25: Accepted. The IdP decides who exists, accounts link only through what the IdP asserted, and person kind and permissions move to per-feature access policies (TASK-129).
