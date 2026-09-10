---
status: Draft
date: 2026-09-10
applies: target
scope: How the app identifies people across workplace systems: person records, linked accounts, person kinds, storage, and where a conversation is handled.
---

# People and Accounts

## Context

The bot coordinates people who work in Google Workspace with Slack, in Microsoft 365 with Teams, or in both ([workplace-systems.md](workplace-systems.md)).

- **Google Identity is SRE's primary source for employees,** but some employees never use it and work only from their Microsoft identity.
- **Addresses don't line up.** A person's Google and Microsoft sign-in addresses differ, and SRE doesn't control how Microsoft addresses are created. The Google `first.last@domain` pattern isn't enforced; name changes and typos break it.
- **Contractors currently receive employee accounts,** although narrower access is wanted.
- **Partners** may interact directly later; that is out of scope here.

Vendors agree that addresses are not identities:
- Google recommends "not using the user email address as a key for persistent data because the email address is subject to change" ([Directory API guide](https://developers.google.com/workspace/admin/directory/v1/guides/manage-users)).
- Microsoft calls the user object ID "the immutable identifier" and notes a user "contains a different object ID in each tenant" ([ID token claims](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference)).
- OpenID Connect says email and names "MUST NOT be used as unique identifiers"; only issuer plus subject is ([OIDC Core §5.7](https://openid.net/specs/openid-connect-core-1_0.html)).

Current state and known gaps:

- **No person record or people table exists.** DynamoDB is provisioned (`terraform/dynamodb.tf`) and already used through `StorageService` by the access feature, idempotency and audit.
- **Storage can't yet claim an account atomically.** `StorageService` offers `put_if_not_exists` on a single item, but no atomic write across several items, and a unique account claim plus its link needs one.
- **Humans are keyed by email in stored data.** Access request decisions put `actor_email` in their sort key (`packages/access/request/store.py`), and the audit trail table indexes `user_email`.
- **Retro attendees are resolved from Slack profile emails** (`modules/incident/schedule_retro.py`).
- **The Slack runtime lives in `integrations/slack/`,** so callers can't yet be resolved at an entry point ([platform-entrypoints.md](platform-entrypoints.md)).
- **Directory access is Google-only.** `infrastructure/directory/` reads a single Google directory, and there is no Microsoft Graph client.

Open before acceptance (TASK-83.1):

- **Which verified-link mechanisms come first:** SRE admin links; self-service linking, where the person signs in to both accounts; or an HR employee number, if one is populated in both directories (Microsoft Graph `employeeId`, Google Directory `externalIds` of type `organization`).
- **The authoritative source for contractors:** who creates them, and where their kind is recorded.
- **How SRE reviews suggested links at employee scale** without linking automatically.

## Decision

**The app owns the person record.** A `Person` has a stable, app-generated id. New records that refer to a human (incident roles, meeting attendees, approvers, audit actors) store that id, never an email, a name or a vendor user id.

**Accounts are linked, never matched.**

- An `Account` is identified by `(system, tenant, account_id)`, where `account_id` is the vendor's stable id:
  - `google`: the Directory user `id`;
  - `microsoft`: the Entra object id, which covers Microsoft 365 and Teams;
  - `slack`: the user id, scoped by its workspace `team_id`.
- An account keeps known id aliases, because a Slack user id changes when a workspace joins an Enterprise org.
- Emails, UPNs and display names are attributes, refreshed from their source and used for display and lookup. They are never keys.
- Every link from an account to a person records its provenance:
  - `directory`: created from the authoritative source for that kind of person;
  - `admin`: made by SRE;
  - `verified`: the person proved control of both accounts, e.g. by signing in to each;
  - `hr_id`: the same HR employee number appears in both directories.
- Matching emails or names may *suggest* a link for SRE to confirm. They never create one.
- Accounts may exist unlinked, and a person may hold any subset of accounts. A Microsoft-only employee is a person with a Microsoft account, whether or not their Google account is linked.
- Creating or removing a link is audit-logged.

**Kind.** Every person has a kind, `employee` or `contractor`; further kinds such as partner can be added later. Kind comes from the authoritative source, never from an address domain or naming pattern, and features use it for access decisions.

**Authoritative sources.** For now, Google Directory is the authoritative source of employees: employee persons are created from it. Microsoft and Slack accounts are imported unlinked and linked to existing people.

**Storage.** People, accounts and links live in a dedicated DynamoDB table owned by the people capability package ([capability-packages.md](capability-packages.md)), written through the storage capability. Each account is claimed by exactly one person: the claim and the link go in one atomic conditional write, so two people can never hold the same account. Vendors are only read; the people table is the only place identity data is written.

**Homes.** A person has a home account per service kind: chat, calendar and mail, files.
- A home defaults to the account the person actually uses; for chat, that is the platform their requests come from.
- SRE can override a home.
- Features ask for "this person's calendar" or "reach this person" and never choose a system themselves.

**Conversation origin.**
- The platform entry point resolves the caller's account to a person through the people capability, and hands handlers the result: a person, or unlinked ([platform-entrypoints.md](platform-entrypoints.md)).
- A conversation-scoped record, such as an incident, stores its origin as `(platform, tenant, channel_id)` and is handled on that platform.
- Until cross-platform conversations exist, each platform is handled independently. Once they exist, participants on another platform are reached through their chat home.

**Adoption order.** Adoption follows expand, shadow, cut over, contract. People are populated before any consumer reads them. A consumer compares person-based results with its current behavior before switching, and it keeps an explicit, logged fallback for unlinked people until SRE removes it.

## Consequences

- Email joins stop, so renamed users, typos and differing Google and Microsoft addresses no longer break resolution.
- Microsoft-only employees become first-class instead of hiding behind an unused Google account.
- Contractor access can be limited by kind, not by address guesswork.
- Cost: linking needs tooling. That means an SRE admin view, bulk review of suggested links, and later self-service verification.
- Cost: the storage capability needs a new atomic multi-item write before the people store can be built.
- A wrong link routes messages or access to the wrong human. Provenance, audit logging, atomic claims and the no-automatic-match rule are the mitigation.
- Person records are personal data: [observability.md](observability.md) redaction rules and [security.md](security.md) least privilege apply.

## Checks

- Review: new stored models refer to humans by person id, not by email or vendor user id.
- Review: no code joins accounts across systems by comparing emails, UPNs or names.
- Tests: linking an account already claimed by another person fails with a conflict and writes nothing.
- Tests: every stored link carries provenance, and link creation and removal emit audit events.
- Review: kind is read from the authoritative source, never derived from an address.

## Migration

Coordinator: TASK-83, in order:
1. Accept the Drafts and answer the open questions (TASK-83.1). Add the atomic multi-item write after TASK-27 (TASK-83.2).
2. Provision the table (TASK-83.3), then build the people capability package (TASK-83.4).
3. Populate:
   - import Google Directory employees (TASK-83.5);
   - import Slack accounts (TASK-83.6);
   - add SRE link administration (TASK-83.7);
   - add the Microsoft Graph client (TASK-83.12), then import Entra accounts (TASK-83.13).
4. Observe in shadow mode: entry-point caller resolution after TASK-26 (TASK-83.8), and the retro attendee comparison (TASK-83.9).
5. Cut over retro attendees with fallback (TASK-83.10).
6. Inventory and migrate email-keyed stored references (TASK-83.11).

Tolerated until then:
- no people table and no person record;
- email-based resolution in legacy modules;
- `actor_email` sort keys in access request decisions and the `user_email` audit index;
- existing records that refer to humans by email or Slack id.
