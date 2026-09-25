---
status: Accepted
date: 2026-09-25
applies: target
scope: How the app decides what a caller may do on every entry point, how long it trusts a decision, and how IdP group memberships are requested, granted and reviewed.
---

# Authorization

## Context

Callers reach the bot through Slack, Backstage and later Teams. The entry point resolves each caller to a person, or marks them unlinked ([people-and-accounts.md](people-and-accounts.md)). The IdP (Google Workspace Enterprise today; Entra ID later, or both at once) is the source of truth for identity and for group membership.

Current state:
- **Three unrelated mechanisms.** HTTP routes require scopes in the Backstage-issued JWT (`sre-bot:access-requests`, `sre-bot:access-sync`, `sre-bot:access-catalog`, in `infrastructure/security/current_user.py`), and Backstage decides who gets them. Legacy Slack AWS commands call `is_user_member_of_groups` (`modules/permissions/handler.py`), which lists each group in `AWS_ADMIN_GROUPS` and compares emails, so nested groups are missed. The access feature resolves approvers inside its own service.
- **No rule for Slack guests or unlinked callers.**
- **No caching.** `DIRECTORY_CACHE_TTL_SECONDS` exists but no provider reads it.
- **The access feature (`packages/access/`) predates `decisions/`.** It is an early attempt, not a reference; this record sets the target and that code is realigned to it.

Current practice:
- **Declared permissions, central mapping.** Features declare permissions, and one central policy maps IdP groups to roles and roles to permissions. Argo CD ([RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)) and Backstage ([permissions](https://backstage.io/docs/permissions/overview)) work this way. Microsoft warns that an app authorizing on group names or ids "will break in the next tenant" ([app roles](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)).
- **Deny by default, check every request** ([OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)).
- **The IdP doesn't re-check an app's roles.** Google, Slack and Entra session settings don't re-check group-derived roles inside a relying party ([Google session length](https://knowledge.workspace.google.com/admin/security/set-session-length-for-google-services), [Entra CAE](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-continuous-access-evaluation)), so the app owns its decision lifetime. OWASP sets an absolute timeout of 4–8 hours ([Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)); NIST allows at most 24 hours at AAL2 ([SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html)).
- **Governance controls.** Membership governance requires approval by defined roles, separation of duties, time-bound temporary access, automatic audit and periodic review ([NIST SP 800-53 r5 AC-2, AC-5, AC-6](https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-2/)). CCCS prescribes just-in-time access for elevated privileges ([ITSM.10.008](https://www.cyber.gc.ca/en/guidance/zero-trust-approach-security-architecture-itsm10008)).
- **Google membership APIs.** The app reads Google through the Admin SDK Directory API only (`admin.directory_v1`). `members.hasMember` checks one user against one group, counting nested membership when both are in the same domain ([hasMember](https://developers.google.com/workspace/admin/directory/reference/rest/v1/members/hasMember)). Directory groups carry no security-group label. Directory reads are limited to 2,400 queries per minute per user per project ([limits](https://developers.google.com/workspace/admin/directory/v1/limits)). Google can expire MEMBER-role memberships natively, but only through the Cloud Identity API, which the app doesn't use ([membership expiry](https://docs.cloud.google.com/identity/docs/how-to/manage-expirations)). Workspace has no native access-review campaign and sends no Shared Signals events to third parties ([Workspace shared signals](https://developers.google.com/workspace/shared-signals)).

## Decision

**The bot decides, on every entry point.** Authorization is host code in `app/server/security/`, behind the current-user contract in `app/contracts/`. Slack, Teams and Backstage callers all go through the same policy. Backstage token scopes only say that a caller may use the bot API; they grant no feature permission.

**Features declare permissions; they never name groups.**
- A feature declares its permission ids (for example `incident.declare`) through the host's extension point at startup. Each permission has a default level:
  - `everyone`: any caller, including unlinked callers and Slack guests;
  - `authenticated`: a caller resolved to an active person;
  - `role`: an active person holding a role that grants the permission.
- The central configuration ([configuration.md](configuration.md)) maps roles to permissions, and roles to IdP group references `(idp, tenant, group_id)` with a display label. Group names are never keys. A role may list groups from several IdPs, and a person's roles are the union across their linked identities. A join that adds an identity ([people-and-accounts.md](people-and-accounts.md)) discards the person's cached verdict, so the added roles are checked with the IdP.
- Moving to Entra, or adding it, changes that configuration and the directory adapters, not the features.
- A feature checks a permission through the contract and never reads group membership itself. Object-level checks (who may act on *this* resource) stay in the feature's service layer ([security.md](security.md)).
- Deny by default: an undeclared permission, or a permission not granted, is refused.

**Membership is read from the IdP, one role at a time.** A permission check resolves only the role the permission needs. It asks the IdP whether the person's identity is in any of that role's groups, stopping at the first yes, and caches the answer per (person, role) for the decision lifetime. On Google this is Directory `members.hasMember`, so nested groups in the same domain count. Groups are listed explicitly by id in the role configuration; the bot doesn't check group labels. The Entra adapter will use Graph `checkMemberGroups`.

**Decision lifetime.** The bot keeps a short-lived verdict, not permissions.
- A caller's active status and each role answer are trusted for a configurable lifetime, 15 minutes by default (5 to 60), then re-checked with the IdP.
- A time-bound grant ends on the bot's own clock. Its `expires_at` is kept in the bot's grant record from the approval, and no verdict outlives it, whatever the IdP holds. The bot never reads an IdP's expiry field, since IdPs differ on whether they have one.
- Before a privileged permission is used, the bot re-checks active status and membership with the IdP, whatever the cached verdict says.
- After an absolute ceiling of 8 hours, the caller is resolved again through the entry point.
- Each decision is logged with `decided_at`, `source` (cached or re-checked) and `expires_at`.
- **If the IdP is unreachable** once a verdict has lapsed:
  - privileged and state-changing actions are refused;
  - non-privileged reads keep the last verdict for at most 15 more minutes, never past a grant's `expires_at`, with an alert and an audit entry;
  - `everyone` permissions are unaffected.

**Memberships are requested in the bot and written to the IdP.** The IdP stays the system of record.
- Requests run on the approvals capability ([approvals.md](approvals.md)). A git-reviewed catalogue of requestable groups states, for each group:
  - who may request it;
  - the approver group;
  - whether a justification or ticket is required;
  - whether it is privileged, and its maximum duration.
- The approver is never the requester and must be in the approver group; every decision is audited.
- On approval, the effect writes the membership to the IdP.
- **Only privileged roles are time-bound.** Their grants record `expires_at` in the bot, which ends the role in the bot on time. At expiry, the effect removes the membership from the IdP, with retries. An IdP-native expiry may also be set where the adapter supports one, so removal happens even if the bot is down; today that would mean adding the Cloud Identity API. Baseline roles are standing memberships.
- A scheduled comparison of IdP memberships against the catalogue reports members added directly in the IdP to the group's owners and SRE. It never removes anyone.
- Periodic access reviews of standing memberships are required. How reviewers are asked is designed in TASK-130.

**What the access feature becomes.** Each part is realigned to this record:
- `access/catalog` becomes the git-reviewed catalogue of requestable groups, keyed by group id; groups are no longer derived from a naming convention.
- `access/request` is rebuilt on the approvals capability, with the catalogue's approver groups, no self-approval, and an IdP expiry on privileged grants.
- `access/sync` stays: it provisions downstream platforms such as AWS Identity Center from IdP group membership, which is this model's intent.
- Its HTTP routes declare permissions instead of Backstage scopes.

**Not now: push revocation.** Google Reports `activities.watch` (suspension and group-member events) and, later, Microsoft Graph change notifications are the upgrade path for invalidating verdicts sooner. Google documents its push channel as not fully reliable, so push would only shorten the lifetime, never replace it.

## Consequences

- One policy, audited in one place, for every entry point. Backstage no longer needs per-feature scopes.
- Removing someone from a group in the IdP takes effect within 15 minutes, and immediately for privileged actions.
- An IdP outage blocks privileged work after at most 15 minutes, and non-privileged reads after 30.
- IdP read volume, per 15-minute lifetime: one status read per active caller, plus one `hasMember` call per (caller, role used) for each group tried until the first yes, plus the same again for each privileged action. The people import adds users ÷ 500 list calls per run. For 300 active callers using one or two roles, that is roughly 40–100 calls a minute, well under the Directory limit of 2,400 per minute.
- The bot's grant record and its removal at expiry work the same on any IdP. The removal is a scheduled bot job, so while the bot is down, the IdP still lists an expired member, although the bot itself no longer grants the role. Native expiry (Cloud Identity on Google; ID Governance or PIM licences on Entra) would close that gap, and is an optional upgrade.
- Cost: the approvals capability, the catalogue and the membership comparison must exist before the bot grants anything. Until then, memberships are managed in the IdP console.

## Checks

- import-linter: features and capabilities never import `server.security` or a directory adapter to check membership.
- grep: no feature settings slice or feature module contains a group email or group id used for authorization.
- Tests: an undeclared or ungranted permission is refused; an unlinked caller reaches only `everyone` permissions; a Slack guest is treated as unlinked.
- Tests: after the lifetime lapses, the next check calls the IdP; a privileged permission always calls the IdP; with the IdP failing, a privileged action is refused and a non-privileged read is allowed only within the grace period.
- Tests: an approval by the requester, or by someone outside the approver group, is refused; a privileged grant records `expires_at`, and after it no verdict grants the role, even if the IdP still lists the membership.
- Tests: a permission check calls the IdP only for the groups of the role that permission needs, and reuses the (person, role) answer within the lifetime.
- Review: every new route or command declares its permissions, and none relies on a Backstage scope beyond API access.

## Migration

Tickets: TASK-129 (this record and its follow-ups), TASK-116 (`app/server/security/` and the current-user contract), TASK-60 (approvals capability), TASK-130 (access-review design).

Tolerated until then:
- Backstage per-feature scopes on the access routes;
- `is_user_member_of_groups` and `AWS_ADMIN_GROUPS` in legacy Slack AWS commands;
- approver resolution and group writes inside `packages/access/`;
- no decision lifetime and no membership comparison.

**Changes:**
- 2026-09-25: Accepted.
- 2026-09-25: membership checks use the Directory API `members.hasMember` per role, and time-bound grants end on the bot's own grant record, not an IdP expiry field.
