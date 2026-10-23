---
id: TASK-163
title: >-
  Edge allow-list follows the route table: open the authenticated /api/v1 routes
  in the WAF and verify the Backstage key set is reachable from the service
status: To Do
assignee: []
created_date: '2026-10-23T16:26:00Z'
updated_date: '2026-10-23T18:09:00Z'
labels:
  - security
  - configuration
dependencies: []
references:
  - https://github.com/cds-snc/sre-bot/issues/1784
priority: medium
ordinal: 434000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The WAF AuthorizedEndpoints rule (terraform/waf.tf:181-186) blocks every path not in var.authorized_endpoints_with_constraints (terraform/variables.tf:56-71). That list holds only the legacy root paths (/geolocate, /access, /hook, /version, /health, ...), so every /api/v1/* route, which the ADRs make the target HTTP surface and which authenticates with Backstage JWTs, answers 403 at the edge. Nothing in production calls an /api/v1 route today (the access features are disabled), so nothing is broken yet. It becomes a blocker as soon as a Backstage-facing /api/v1 route goes live or a legacy route is retired in favour of its /api/v1 home (TASK-53 step 3). It blocks no configuration-chain task (TASK-111.9 included).

Second, unverified link: the issuers' jwks_uri (https://backstage.cdssandbox.xyz/api/auth/.well-known/jwks.json) answers 403 from outside the CDS network. JWT validation needs the ECS tasks' egress (NAT gateway IPs) to reach it; whether Backstage allows that is unknown.

No ADR covers the edge. decisions/security.md has no rule tying the edge allow-list to the routes the app serves, so it is hand-kept and drifts. OWASP API Security Top 10 2023 API9 (Improper Inventory Management) names that drift; positive-security tooling keeps the allow-list in sync with the API definition.

Scope:
- security.md amendment: the WAF is a positive allow-list kept in sync with the app's mounted routes by a CI check; authentication stays the app's job.
- Terraform: allow the /api/v1 prefix (or the authenticated route prefixes) in authorized_endpoints_with_constraints.
- A CI test compares the mounted FastAPI routes with the terraform allow-list and fails on a route the edge would block, unless that route is listed as intentionally internal.
- Human, with the Backstage owners: confirm the sre-bot NAT egress IPs can fetch the jwks_uri.
- Post-deploy end-to-end token check: a Backstage token with an sre-bot scope gets a non-401/403 answer from one /api/v1 route; a bad token gets 401.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/security.md records the edge rule: the WAF allow-list is derived from or checked against the app's mounted routes, and authentication stays in the app
- [ ] #2 terraform authorized_endpoints_with_constraints allows the authenticated /api/v1 routes; the tf_plan shows only the WAF rule change
- [ ] #3 A CI test fails when a mounted route is blocked by the terraform allow-list and is not listed as intentionally internal
- [ ] #4 The sre-bot ECS egress can fetch the Backstage jwks_uri (evidence in the notes)
- [ ] #5 After apply: one /api/v1 route returns 401 with WWW-Authenticate: Bearer for a bad token and a non-401/403 status for a valid Backstage token
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
