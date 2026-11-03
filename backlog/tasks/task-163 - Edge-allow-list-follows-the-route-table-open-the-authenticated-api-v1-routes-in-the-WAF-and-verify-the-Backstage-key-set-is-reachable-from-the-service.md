---
id: TASK-163
title: >-
  Edge allow-list follows the route table: open the authenticated /api/v1 routes
  in the WAF and verify the Backstage key set is reachable from the service
status: In Progress
assignee: []
created_date: '2026-10-23T16:26:00Z'
updated_date: '2026-11-03T21:45:00Z'
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
- [x] #1 decisions/security.md records the edge rule: the WAF allow-list is derived from or checked against the app's mounted routes, and authentication stays in the app
- [x] #2 terraform authorized_endpoints_with_constraints allows the authenticated /api/v1 routes; the tf_plan shows only the WAF rule change
- [x] #3 A CI test fails when a mounted route is blocked by the terraform allow-list and is not listed as intentionally internal
- [ ] #4 The sre-bot ECS egress can fetch the Backstage jwks_uri (evidence in the notes)
- [x] #5 After apply: an /api/v1 path is answered by the app (not a WAF 403) and /docs and /openapi.json answer 200, shown by deploy-checks post edge; the bad- and valid-Backstage-token checks run with the first PR that makes an authenticated /api/v1 route live (TASK-53 step 3 or TASK-165.2)
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #7 The edge allow-list lives in one file, terraform/authorized_endpoints.json, read by terraform (local.authorized_endpoints feeding the AuthorizedEndpoints rule) and by the CI test; variables.tf no longer holds a copy
- [x] #8 The CI route inventory is generic: it loads every sre_bot entry point (enabled or not) onto the app built by create_app and fails if its plugin set differs from the installed entry points, so routes of future plugins are checked with no change to the test
- [x] #9 The CI test also fails on an allow-list entry that matches no mounted route and is not ALB-served, and on an intentionally-internal route that the allow-list does not block; every mounted route is allowed unless listed intentionally internal with a reason (the list starts empty; the FastAPI docs and /v1/geolocate are allowed); the six legacy entries with no mounted route (/auth/me, /request_access, /active_requests, /past_requests, /accounts, /access) are deleted
- [x] #10 The CI test fails when a route under /api/v1/ has no get_current_user dependency and is not in an explicit public-by-decision set (today /api/v1/hook/{webhook_id})
- [x] #11 bin/deploy-checks.zsh has an edge post check (app answer, not WAF 403, on an /api/v1 path; 401 with WWW-Authenticate for a bad token; optional valid-token probe from the environment) and the stale TASK-163 comment in its HTTP section is removed
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan approved 2026-11-03 (human): OQ1 single /api/v1/ prefix, OQ2 shared JSON file, OQ3 AC #5 split, OQ4 to TASK-37.4; docs public, internal list empty, dead entries deleted on route-inventory evidence.

## Findings that shape the plan (read 2026-11-03)

- WAF: terraform/waf.tf:181-217 (rule AuthorizedEndpoints, priority 6, block if NOT any byte_match on uri_path, text_transformation NONE) fed by var.authorized_endpoints_with_constraints (terraform/variables.tf:40-71, only consumer waf.tf:194, no tfvars/terragrunt override). Other rules that touch /api/v1 traffic: CommonRuleSet (waf.tf:43-79) is scoped down only for "/hook/" STARTS_WITH, so /api/v1/* POST bodies over 8 KB hit SizeRestrictions_BODY (AWS: ALB body inspection limit 8 KB, rule blocks >8,192 bytes), query strings >2,048 bytes and paths >1,024 bytes are blocked; rate rules 0/7 are per-IP/constant and unaffected by path.
- Routes actually mounted (probed by booting pluggy with ALL 9 entry points, no lifespan): / , /version, /health, /geolocate/{ip}, /hook/{webhook_id} (allowed today); /api/v1/hook/{webhook_id}, /api/v1/access/{sync-runs,requests,catalog}/... (7+2+2 routes), /v1/geolocate (packages/geolocate/routes.py:11 prefix "/v1", mounted at root by packages/geolocate/__init__.py:31), /docs, /docs/oauth2-redirect, /redoc, /openapi.json (all blocked today).
- Production mounts NO authenticated /api/v1 route: access.catalog/request/sync are false in every environment (app/config/base.toml:257-261). So AC5 (valid-token answer) cannot be exercised until a route is live; see Open question 3.
- Allow-list entries matching no mounted route: /auth/me, /request_access, /active_requests, /past_requests, /accounts, /access (legacy Flask-era, no match under app/ outside tests/meet). /.well-known/security.txt is served by the ALB (terraform/alb.tf:62-86), not the app.
- FastAPI 0.156.8 nests routers (`_IncludedRouter`): app.routes has no `.path` on every item; use the public fastapi.routing.iter_route_contexts(app.routes) (gives path, methods, original_route.dependant).
- Auth: infrastructure/security/current_user.py:57-133 returns 401 + WWW-Authenticate: Bearer (lines 89-95) for a missing/invalid token and 403 for missing scopes. JWKS client is lazy (jwks.py:54-90, warmup only builds clients), so an unreachable jwks_uri first shows as `jwt_validation_failed` (jwt.py:141) on the first valid-shaped token, not at boot.
- No python-hcl2 dependency (rg over app/pyproject.toml and uv.lock). Existing check pattern: app/bin/check_*.py + Makefile + ci_code.yml; tests that boot the app use a fresh-interpreter subprocess (tests/integration/server/boot_probe.py, tests/unit/server/test_server_app_import_*_lazy.py).
- Deployment mechanics (decisions/deployment.md:14): tf_apply.yml applies on push to main touching terraform/**; build_and_deploy.yml skips only if ALL changed paths are ignored, so this PR (touches app/tests) also triggers a routine app deploy of unchanged runtime code.

## Design

1. One machine-readable source: terraform/authorized_endpoints.json (list of {path, positional_constraint, note}). Terraform reads it (`jsondecode(file(...))` in a local); the test reads the same file with stdlib json. No HCL parsing, no new dependency, no regex over variables.tf. variable "authorized_endpoints_with_constraints" is removed (single consumer) so there is not a second copy to drift.
2. Edge granularity: one new entry { "/api/v1/", STARTS_WITH }. The edge allows the versioned API surface; authentication and authorization stay in the app (security.md, authorization.md untouched). A route family outside /api/v1/ (tomorrow anything) is caught by the test and needs its own entry. Today's root-mounted routes the edge blocks by accident get entries: the FastAPI docs (/docs, /docs/oauth2-redirect, /redoc, /openapi.json: the code is open source and the docs are public by decision, human 2026-11-03) and /v1/geolocate (EXACTLY; the duplicate of the legacy /geolocate/{ip} is TASK-124.6's to resolve).
3. Generic route inventory (no hand list of routes): a fresh interpreter builds `server.server.create_app()` on the ci configuration (static mounts + FastAPI docs routes), then loads EVERY entry point of group sre_bot into a new pluggy manager (hookspecs FeatureLifecycleSpecs, load_setuptools_entrypoints, nothing blocked, so disabled plugins count) and calls register_routes on that app, then walks iter_route_contexts. Any future plugin (incident HTTP base in TASK-165.2, API MVP in TASK-165.3) or any router added in server.py/api/router.py is covered with no change to this check. Unknown route types (Mount, WebSocket) fail the check instead of being skipped.
4. "Blocked" = the WAF's own semantics: EXACTLY compares the whole template (a template containing "{" never matches EXACTLY); STARTS_WITH compares the literal head of the template (text before the first "{"); any other positional constraint raises (fail closed, extend deliberately). Case sensitive, no decoding (matches text_transformation NONE).
5. Edge rule (human, 2026-11-03): every route the app mounts is reachable at the edge; the allow-list exists to drop requests for paths the app does not serve (scanner and fuzzing noise, forgotten or framework-default paths), never to hide a served route; hiding is not a control (the code is public) and access control is the app's authentication. Intentionally internal = a mounted route the edge must block, each with a reason; the list lives in the test, starts EMPTY, and is enforced both ways (a listed route that is allowed or no longer mounted fails: shrink-only). It stays so a future route that must not face the internet (for example a metrics or admin endpoint) is a reviewed decision, not an accident.
6. Compensating control for opening a prefix: the same inventory asserts every route under /api/v1/ depends on get_current_user, except an explicit PUBLIC_BY_DECISION set (today /api/v1/hook/{webhook_id}: webhook tiers in security.md; TASK-37.4 keeps both mount points). This enforces security.md "routes are authenticated by default" at the point the edge stops filtering.

## Steps (ordered; TDD: tests first)

1. Tests first (red), app/tests/utils/edge_allow_list.py (matcher, JSON loader, probe source, ~90 LOC test code) + two test files (matrix below). They fail until steps 3-4.
2. Dead entries deleted (human, 2026-11-03: there is no bot frontend; the surfaces are Slack, Teams and the Backstage backend plugin calling with Backstage tokens validated against JWKS, people-and-accounts.md): /auth/me, /request_access, /active_requests, /past_requests, /accounts, /access. Evidence: the route inventory shows no mounted route behind any of them, so a request that passes them today gets a 404 from the app; removing them only turns that 404 into a WAF 403. No WAF-log query needed.
3. Terraform: create terraform/authorized_endpoints.json (current entries minus the six dead ones, plus the four docs routes and /v1/geolocate, plus {"/api/v1/", STARTS_WITH}, a "note" per entry, security.txt noted as ALB-served); terraform/local.tf add `authorized_endpoints = jsondecode(file("${path.module}/authorized_endpoints.json"))`; terraform/waf.tf:194 for_each = local.authorized_endpoints; delete the variable at terraform/variables.tf:40-71. PR tf_plan must show only the AuthorizedEndpoints statement list changing.
4. Decision record: decisions/security.md new "Edge" paragraph in Decision, one line in Checks, dated line in Changes: the WAF AuthorizedEndpoints rule is a positive allow-list of API surfaces kept in sync with the mounted routes by a CI test over the plugin-loaded route table (routes blocked on purpose are listed in that test); authentication and authorization stay in the application; the edge never replaces route-level auth; cites OWASP API9:2023 (https://owasp.org/API-Security/editions/2023/en/0xa9-improper-inventory-management/) and AWS WAF managed-rule/positive-security guidance. No change to authorization.md, plugins.md (consumes register_routes as is) or the permission mapping.
5. bin/deploy-checks.zsh: add task check `edge` (post only; kept until the first PR that makes an authenticated /api/v1 route live has run it with a token, TASK-53 step 3 or TASK-165.2; TASK-164 moves it into CI): (a) unauthenticated GET to an /api/v1 path returns an app response (JSON content-type; 401 + `WWW-Authenticate: Bearer` when a route is live, 404 JSON while none is) and not the WAF 403, and GET /docs and /openapi.json answer 200; (b) bad token gives 401 + WWW-Authenticate; (c) when SREBOT_PROBE_TOKEN is in the environment (never printed), a valid token gives a status outside {401,403}; path from EDGE_PROBE_PATH, default an unmounted /api/v1 path; (d) Logs Insights count of jwt_validation_failed since the rollout (informational). Update the HTTP section header comment at deploy-checks.zsh:176 (stale "403 at the WAF until TASK-163") and usage text at lines 4-14.
6. Human, before merge: confirm with the Backstage owners that the sre-bot NAT egress IPs may fetch https://backstage.cdssandbox.xyz/api/auth/.well-known/jwks.json (IPs from `aws ec2 describe-nat-gateways`, read-only); evidence = their written confirmation in the notes. Empirical proof comes with the first live authenticated route.
7. Verification: ruff + the two targeted test files while building; then once each, sequentially: `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `cd app && uv run pytest tests --ignore=tests/smoke`; also `make check-import-contracts` and `make check-settings-key-ownership`. Human: `zsh bin/deploy-checks.zsh pre` before merge (rollback tag), after merge wait for tf_apply and the app deploy, then `zsh bin/deploy-checks.zsh post edge`.

## Test matrix

app/tests/unit/server/test_server_edge_allow_list_matcher.py (pure, synthetic inputs)
- EXACTLY matches the identical path only; STARTS_WITH matches the head of a templated route (/hook/{id} vs /hook); a templated route never matches EXACTLY; "/api/v1/" does not match "/api/v10/x" or bare "/api/v1"; unsupported constraint (CONTAINS) raises; case differs = blocked; unknown route type in the inventory fails.
- Failure report names method, path and the file to edit; a synthetic new "/api/v2/x" route fails; a synthetic internal-listed route that becomes allowed fails; a stale internal or public entry (route not mounted) fails; an allow-list entry matching no route and not ALB-served fails.
app/tests/unit/server/test_server_edge_allow_list_routes.py (fresh-interpreter inventory over the real tree + real JSON)
- Every mounted route is allowed or listed internal (happy path on the repo as it will be).
- The inventory covers every entry point: its plugin set equals installed_plugin_names() (a skipped plugin fails; this is the generic guard for future incident packages).
- Every allow-list entry matches a mounted route or is ALB-served; every internal route is blocked.
- Every /api/v1/ route outside PUBLIC_BY_DECISION depends on get_current_user (authorization case); the public set has no stale entry.
- terraform/waf.tf consumes local.authorized_endpoints and local.tf reads authorized_endpoints.json (wiring pin, as in the settings-ownership check test).

## AC traceability
AC1 -> step 4 (security.md) + wiring pin. AC2 -> step 3 (+ step 2 for deletions, docs and /v1/geolocate entries). AC3 -> step 1 test files, green only with steps 3-4. AC4 -> step 6. AC5 -> step 5 (edge part now; token part when a route is live, OQ3). AC6 -> step 7. AC7 (single JSON source) -> step 3 + wiring pin. AC8 (generic inventory) -> design point 3 + the plugin-set-equals-entry-points test. AC9 (reverse check, internal enforcement, dead-entry deletion) -> steps 1-3. AC10 (auth-by-default under /api/v1/) -> design point 6 + step 1. AC11 (edge deploy check) -> step 5. Every step maps to an AC.

## Size and gate
Production files: terraform/authorized_endpoints.json (new, ~20 lines), terraform/local.tf (+3), terraform/waf.tf (1 line), terraform/variables.tf (-32), decisions/security.md (~+10), bin/deploy-checks.zsh (~+45) = 6 files, ~110 changed LOC. Test code (not counted): 3 files, ~250 LOC. Subsystems: terraform plus an app test; the ADR and a dev shell helper are support. No mechanical refactor mixed with behavior, no app runtime code. Gate does not trip; one PR as doc-11 row 9b states. If the reviewer counts deploy-checks.zsh as a third subsystem, the separable cut is step 5 into a follow-up (it needs no app or terraform code); the test and the terraform change cannot be split from each other (the test fails against the old list).

## Blast radius and rollback
- Only the AuthorizedEndpoints rule changes. Widening: /api/v1/* now reaches the app; mounted there in production: /api/v1/hook/{webhook_id} only (same handler, rate limit and body cap as /hook/{id}, but CRS is not scoped down for that prefix, so JSON senders may be blocked by CRS: today's behavior at that path is a WAF 403 anyway). Also widened: /docs, /redoc, /openapi.json, /docs/oauth2-redirect and /v1/geolocate (public, unauthenticated, already in the open-source repository; /v1/geolocate is the same lookup as /geolocate/{ip}, rate-limited by the same WAF rules). Narrowing (6 dead entries): no mounted route behind them, so 404 becomes 403. A malformed JSON or bad constraint fails at tf_plan on the PR, before any apply.
- Rollback: one git revert of the merge commit; tf_apply.yml re-applies on that push (group terraform-apply, serial). WAF change is an in-place web ACL update; no task restart. The accompanying app deploy is unchanged runtime code; deploy rollback per docs/runbooks/roll-back-a-deployment.md with the image_tag printed by deploy-checks pre. Ordering: merge, wait for tf_apply to finish, then run post edge; the human JWKS confirmation precedes any live authenticated route, not the merge.

## Assumptions and doubts (verify)
- Plugin import in a fresh interpreter has no side effects needing configuration (verified by a probe on 2026-11-03: all 9 loaded without lifespan); create_app() under a minimal environment (ENVIRONMENT=ci, no SLACK__* vars) builds. Verify in step 1; fallback is bare FastAPI + api.router.api_router plus a pin that server.py mounts nothing else.
- iter_route_contexts is public in the pinned fastapi 0.156.8; a fastapi bump re-runs the test (it is the dependency-change signal).
- terraform/ is present in every pytest run (checkout in CI and the devcontainer); the test fails, never skips, if the JSON is missing. Verify tests are not run from the container image (ci_container.yml).
- The ALB evaluates WAF before listener rules, so /.well-known/security.txt must stay in the list. Verify via the plan staying free of changes for that entry.
- Oversize POST bodies (>8 KB) on future /api/v1 routes will be blocked by CRS SizeRestrictions_BODY; not changed here (see OQ4).

## Open questions for the reviewer (each with a recommendation)
1. Edge granularity: single "/api/v1/" prefix (chosen) vs one entry per route family (/api/v1/access/, /api/v1/incidents/ ...). Prefix: no terraform edit per new route family (coordinated-incident routes in TASK-165.2/165.3 pass the same check unchanged); cost: /api/v1/hook/{id} becomes edge-reachable. Per-family: tighter, but every new family is a terraform change inside a feature PR.
2. Source of the list: JSON read by terraform and the test (chosen) vs keeping variables.tf and parsing it (regex or a new python-hcl2 dev dependency). JSON removes drift and parsing fragility; comments move into a "note" field.
3. Decided 2026-11-03 (human): AC #5 split. AC5 cannot run in production now (no authenticated /api/v1 route is mounted). Recommend: this task proves the edge is open (app answer instead of WAF 403) and ships the `edge` check; the valid-token/401 check moves to the first PR that makes an authenticated /api/v1 route live (TASK-53 step 3 geolocate move, or TASK-165.2), which runs `deploy-checks.zsh post edge` with a token. Proposed via comment on the task, AC5 not edited.
4. Decided 2026-11-03 (human): out of scope; TASK-37.4 owns the CRS scope-down and body cap for both webhook mount points, and the 8 KB CRS body limit for future incident POST routes is noted on TASK-165.2.
5. Resolved 2026-11-03 (human): docs are public; the landing page /docs link works after apply. Dead entries deleted on the route-inventory evidence, no WAF-log query.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-03 (human): FastAPI docs are public (open-source code; hiding is not a control); the edge rule is 'every mounted route is reachable, the allow-list drops unserved paths'; internal list starts empty; /v1/geolocate gets an entry; the six legacy entries are deleted on the route-inventory evidence (no bot frontend: surfaces are Slack, Teams and the Backstage backend plugin). Plan approved 2026-11-03.

Implemented 2026-11-03 on task-163-edge-allow-list, In Progress.
- terraform/authorized_endpoints.json (new, 12 entries with a note each) is the single allow-list: local.tf reads it (local.authorized_endpoints), waf.tf:194 iterates it, the variable is gone from variables.tf. Added /api/v1/ STARTS_WITH, /docs, /docs/oauth2-redirect, /redoc, /openapi.json, /v1/geolocate; removed /auth/me, /request_access, /active_requests, /past_requests, /accounts, /access. terraform fmt clean, terraform validate OK; tf_plan on the PR is the evidence for AC #2.
- Tests (app/tests/unit/server): edge_allow_list.py (WAF byte-match semantics, drift and auth checks), edge_route_probe.py (fresh interpreter: create_app on ci plus every installed entry point's register_routes, no lifespan, routes walked with fastapi.routing.iter_route_contexts), test_server_edge_allow_list_matcher.py (14 synthetic cases), test_server_edge_allow_list_routes.py (plugin set equals installed_plugin_names, no edge violation, /api/v1 auth-by-default with PUBLIC_BY_DECISION = /api/v1/hook/{webhook_id}, terraform wiring pin). Red first (missing JSON, wiring), then green; mutation check: dropping /docs from the JSON fails with 'GET,HEAD /docs is blocked at the edge'.
- decisions/security.md: Edge paragraph (amended 2026-11-03), Checks line, Changes line; scope line extended. No change to authorization.md or plugins.md.
- bin/deploy-checks.zsh: task check edge (post), probe helper sends a token on curl's stdin; stale TASK-163 HTTP header removed. Read-only probe of production today: /api/v1/edge-probe, /docs and an unknown path answer 403 text/html (WAF); /version 200 application/json. After apply the check expects 404 application/json on the default probe path.
- Gates: ruff clean, format clean, import contracts 13 kept, key ownership OK, mypy 41 errors in 14 untouched legacy files (pre-existing, none in new files), pytest 6052 passed.
Open: AC #2 (tf_plan on the PR shows only the AuthorizedEndpoints statements), AC #4 (Backstage owners confirm the NAT egress may fetch the jwks_uri), AC #5 (post edge after tf_apply and the deploy).

2026-11-03 merged (#1816, 023aa1e5, 21:19Z); Terraform Apply success; deployed on sre-bot-task:77 (image tag 023aa1e55636f198ffad49399c27971536c34fb9-2026-11-03).
- AC #2: PR tf_plan 'Plan: 0 to add, 1 to change, 0 to destroy' (aws_wafv2_web_acl.sre-bot in place). The rule set is re-rendered as a whole; the multiset diff of removed vs added lines differs only in AuthorizedEndpoints search strings: removed /access, /accounts, /active_requests, /auth/me, /past_requests, /request_access; added /api/v1/, /docs, /docs/oauth2-redirect, /redoc, /openapi.json, /v1/geolocate. The managed rule sets come back identical.
- AC #5: zsh bin/deploy-checks.zsh post edge (tmp/deploy-checks/post-edge-20261103T214306Z.txt, 21:43Z): rollout PASS, slack_up PASS, version PASS (023aa1e5), runtime_errors PASS; GET /api/v1/edge-probe without a token 404 application/json (the app, not the WAF 403): edge_api_reaches_app PASS; edge_docs_docs PASS; edge_docs_openapi_json PASS; edge_bad_token SKIPPED (no live authenticated /api/v1 route; the token checks run with TASK-53 step 3 or TASK-165.2, per the AC). jwt_validation_failed 0.
- Not from this change: the deploy job failed (the known bake-time race, TASK-164; rollout COMPLETED, 2/2 running); boot_errors FAIL on 3 slack_listener_error view_submission lines at 21:23-21:24Z (user modal submissions; this PR changed no app runtime code, and the 2026-10-29 pre baseline also has one). non_json_lines WARN (4 known import-time lines).
Open: AC #4 (Backstage owners' written confirmation that the NAT egress may fetch the jwks_uri; required before the first live authenticated route).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T20:20:00Z

---

Planning finding for AC #5: production mounts no authenticated /api/v1 route (access.catalog/request/sync are false in every environment, app/config/base.toml:257-261), so a valid-token answer cannot be observed after this apply. Proposal for the human: AC #5 splits into (a) now, an /api/v1 request reaches the app instead of the WAF 403, and a bad token gets 401 + WWW-Authenticate once a route is live; (b) the valid-token check runs with the first PR that makes an authenticated /api/v1 route live (TASK-53 step 3 or TASK-165.2) using deploy-checks post edge. AC #4 evidence now is the Backstage owners' written confirmation; empirical proof arrives with (b). AC left unedited.

---
<!-- COMMENTS:END -->
