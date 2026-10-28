---
id: TASK-166
title: >-
  Access rebuild: just-in-time access to many platforms, API first, over the
  shared capabilities
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
updated_date: '2026-10-28T19:42:00Z'
labels:
  - access
milestone: m-7
dependencies:
  - TASK-167
type: feature
ordinal: 438000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
PROBLEM
There is no supported way to request elevated access. Many SaaS platforms, AWS among them, need just-in-time access or SCIM-like provisioning, and many integrate poorly with Google. Slack may be replaced by Teams and Google by Entra ID; a merger may mandate an identity governance tool or refuse the bot write access to its IdP. The existing access package predates the ADRs and is disabled in production: about half of it is general-purpose code that now has a home elsewhere.

DECISIONS
- Keep and rebuild the access feature; do not adopt an AWS-only tool. It is delivered after incident management.
- API first: the HTTP API defines the behaviour; every surface is a thin client. Slack first, a Backstage plugin when adoption justifies it, Teams if procurement requires it. No rules or state in Slack handlers.
- Access keeps only the requestable-entitlement catalogue, an approval policy, grant records and platform adapters. The approval engine moves to the approvals capability (access supplies a policy and an effect handler); identity moves to the people capability (person ids, never emails); group reads and writes to the directory capability, one adapter per IdP; authorization to declared permissions mapped to IdP groups; messages to the notifications capability; runtime config loaders, in-process events, background threads and the managed-group naming convention are deleted.
- A grant is desired state for the reconciler: desired access = IdP group entitlements plus active grants. Approval writes the grant and reconciles that person; expiry, scheduled start, drift reports and revoke-after-outage come from the scheduled reconcile. Drift is reported, never removed automatically, unless a platform is set to remove. Early revoke sets the expiry to now.
- A catalogue target is an IdP group or a platform entitlement held in the grant record and applied by reconcile, for IdPs that refuse bot writes or platforms with no group mapping. For AWS the unit is an IAM Identity Center group with account assignments managed in Terraform.
- Downstream platform accounts are linked to people by the platform account id when the bot provisions them, otherwise by SSO email or an admin link.
- EN/FR everywhere: catalogue labels carry both languages, validated at boot; proactive messages use each person's preferred official language, falling back to bilingual. Web surfaces meet CAN/ASC-EN 301 549 with a conformance assessment before release.
- The removal mode of each platform's sync is chosen deliberately; a failed IdP read never removes access.

This coordinator is broken out into subtasks as the ADRs are amended (people and IdP writes, authorization targets, approvals continuation, i18n preferred language, a new accessibility record).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The ADR amendments for IdP writes, platform-entitlement targets, the in-feature approval effect, preferred language and accessibility are recorded
- [ ] #2 Subtasks cover the shared prerequisites (security permissions, approvals, people, directory, notifications), the move and strip to app/features/access, the reconcile core with grants, the catalogue, request, the Slack surface and the AWS Identity Center adapter, each a single PR
- [ ] #3 An approved AWS request grants access within seconds and is removed at expiry by reconcile, including after the bot was down
- [ ] #4 A developer can run the access plugins locally: the AWS profile and cross-account permissions they need are documented, and the plugins are switched on through PLUGINS__PLATFORM_ACCESS in app/.env
- [ ] #5 The entitlement catalogue is managed content (decisions/organisation-content.md, managed-content.md): one validated, authorised, versioned and audited write path, read through a port the access feature owns; ACCESS_CONFIG_SOURCE and its four loaders are deleted
<!-- AC:END -->
