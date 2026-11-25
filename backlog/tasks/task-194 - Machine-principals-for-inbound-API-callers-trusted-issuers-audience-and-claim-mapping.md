---
id: TASK-194
title: >-
  Machine principals for inbound API callers: trusted issuers, audience and
  claim mapping
status: To Do
assignee: []
created_date: '2026-11-25T20:49:00Z'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-168
references:
  - decisions/security.md
  - decisions/service-accounts.md
  - decisions/authorization.md
priority: high
ordinal: 551000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Decide and build machine-principal authentication for inbound API callers (TASK-168 research packet section 5, row NEW-A, Q9 and OQ25). Infrastructure-owned and independent of the webhook slices; it is the prerequisite for caller class 1. The security.md Webhooks "Machine callers" paragraph (added by TASK-37.1) names the three caller classes and points here; no decision text exists yet.

Caller classes: 1, first-party workloads with an identity (GitHub Actions, Azure Logic Apps and Sentinel playbooks, Backstage, the organisation's own services) call the owning feature's authenticated API under /api/v1/; 2, third parties and AWS services that can only sign use the webhook ingress; 3, legacy secret-URL senders are burned down by TASK-48.

Scope:
- A decision, as a security.md or service-accounts.md amendment: the trusted issuers (the GitHub Actions issuer https://token.actions.githubusercontent.com; the organisation's Entra tenant for managed identities), the audience per deployment, the claim-to-principal mapping (GitHub repository_id plus job_workflow_ref and ref, using immutable ids; Entra oid or appid plus aud), deny by default, and permissions per authorization.md.
- JWKS validation through the existing get_current_user path; issuers, audiences and mappings as typed settings configured per environment.

Out of scope: any feature endpoint (for example the incident alert-intake endpoint, owned by the incident re-cut); a direct-call identity for AWS workloads (not decided; AWS callers stay on SNS).

Size: ~250 production LOC.
Production: prod.
Revert / blast radius: one revert; no route depends on it until a feature endpoint does.
Change notice: developer notice: GitHub Actions and Azure (Sentinel, Logic Apps) can call the bot's API with their own identity; a guide per caller class (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision record amendment (security.md or service-accounts.md) states the trusted issuers, the audience per deployment, the claim-to-principal mapping and deny by default (review)
- [ ] #2 Trusted issuers, audiences and claim mappings are typed settings with defaults, set per environment in the configuration files; make check-settings-key-ownership is green (test + check)
- [ ] #3 A GitHub Actions OIDC token for the configured audience from a mapped repository_id and job_workflow_ref resolves to a machine principal through get_current_user; a wrong issuer or audience, or an unmapped claim set, answers 401 or 403 (tests)
- [ ] #4 An Entra managed-identity token (oid or appid plus aud) resolves to a machine principal the same way (test)
- [ ] #5 A machine principal holds only the permissions granted to it per authorization.md, and this task opens no route (test + review)
- [ ] #6 The PR body carries the developer change notice and links a guide per caller class (review)
<!-- AC:END -->
