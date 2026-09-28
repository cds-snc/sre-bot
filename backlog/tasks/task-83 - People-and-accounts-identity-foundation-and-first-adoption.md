---
id: TASK-83
title: 'People and accounts: identity foundation and first adoption'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:05'
labels:
  - identity
dependencies: []
references:
  - decisions/people-and-accounts.md
  - decisions/workplace-systems.md
  - decisions/platform-entrypoints.md
  - decisions/plugin-architecture.md
priority: medium
ordinal: 167000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. Builds the identity model in decisions/people-and-accounts.md (Accepted 2026-09-25). The app owns the person record. The IdP (Google today; Entra or both later) decides who exists, and platform accounts (Slack, Teams, Backstage) link to people only through what the IdP asserted.

WHY: today the bot identifies humans by email:
- directory lookups use users().get(userKey=email);
- Backstage callers are identified by the token's email claim (infrastructure/security/current_user.py);
- access decisions store actor_email and approver_email;
- the audit trail indexes user_email;
- retro attendees come from Slack profile emails.
Emails change and are reassigned, and a second IdP would give one human two addresses.

CURRENT GAPS (2026-09-25):
- There is no people table and no person record.
- StorageService has no atomic write across several items (TASK-83.2), which an identity or account claim plus its link needs.
- The Slack runtime still lives in integrations/slack/. Resolving callers at the entry point needs TASK-26.
- No Microsoft Graph client exists. It is needed only once Entra becomes a trusted IdP or Teams ships.
- Who may do what is decided separately, by per-feature access policies and IdP groups (TASK-129).

SAFEST SEQUENCE. Each step is reversible, and nothing visible to users changes until shadow data supports it.
0. Decided: the records are accepted. Add the atomic multi-item write after TASK-27.
1. Foundation, no consumers: provision the table, then build the people capability with its in-memory fake.
2. Populate, reading vendors only:
   - import Google Directory users as people with IdP identities;
   - import Slack accounts, linking full SSO members through the sso_email rule;
   - add SRE link administration for exceptions and cross-IdP joins.
   Entra follows the same pattern when it becomes a trusted IdP.
3. Observe: resolve Slack callers at the entry point in shadow mode. Compute retro attendees from people alongside Slack emails, and log the differences.
4. Cut over with fallback: retro attendees come from people; unlinked attendees fall back to their Slack email with a warning.
5. Contract: inventory stored human references keyed by email or vendor id, and migrate each through expand, backfill, switch reads, contract.

RULES FOR EVERY CHILD:
- A link comes only from the IdP import, an IdP subject delivered by the platform, the sso_email rule, or an audited SRE action. Never from a free email or name match.
- Identities from different IdPs are never joined on email.
- Vendors are only read. New writes go to the people table only.
- Jobs and cutovers ship behind settings that default to off.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every child task is Done, completed in the dependency order recorded on the children
- [ ] #2 No consumer switches to person-based resolution before SRE has reviewed a shadow comparison
- [ ] #3 decisions/people-and-accounts.md is Accepted, and its Migration section lists only the gaps still tolerated
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:09
---
2026-09-24 alignment with decisions/plugin-architecture.md: decisions/capability-packages.md is deleted. The people capability lives at app/capabilities/people/ (TASK-83.4). Directory reads go through app/capabilities/directory/ (TASK-119). Caller resolution happens at the Slack entry point in app/server/slack/ (TASK-26.2). The retro shadow and cutover steps (TASK-83.9, TASK-83.10) run on the rebuilt retro surface in app/features/incident/ (TASK-38), because modules/incident is frozen to bug fixes (migration.md rule 1). TASK-83.1 no longer owns the cascade, which commit 3407cd5c applied.
---
<!-- COMMENTS:END -->
