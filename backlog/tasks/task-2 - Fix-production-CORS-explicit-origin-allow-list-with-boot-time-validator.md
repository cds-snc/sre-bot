---
id: TASK-2
title: 'Fix production CORS: explicit origin allow-list with boot-time validator'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-21 17:47'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
references:
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1256'
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (CORS). Today app/server/server.py:21-28 sets allow_origins=["*"] when not bool(app_settings.PREFIX), combined with allow_credentials=True at line 32 - i.e. production gets wildcard origins WITH credentials (SEC-1, OWASP API8:2023).

Steps:
1. Add a CORS_ALLOWED_ORIGINS list field to settings (the SecuritySettings slice if task-24 has landed, otherwise app settings).
2. In app/server/server.py, pass the configured list to CORSMiddleware. Never compute origins from environment shape.
3. Add a boot-time validator (settings model validator or lifespan phase-1 check) that raises if "*" appears in the origins list while allow_credentials is true - in EVERY environment.
4. Populate real origins per environment in deployment config.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CORSMiddleware receives an explicit origin list from settings; no wildcard logic remains in app/server/server.py
- [ ] #2 Boot fails with a clear error when config contains "*" origins together with credentials (test exists)
- [ ] #3 grep: allow_origins is never computed from ENVIRONMENT/PREFIX conditionals
- [ ] #4 CORSMiddleware allow_methods and allow_headers are explicit lists (no "*"), matching allow_credentials=True per FastAPI/Starlette docs and docs/adr/api-security.md's stated method/header set
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Research summary

- Current code (app/server/server.py:21-35, already migrated off PREFIX by TASK-1.2.2):
  allow_origins = ["*"] if app_settings.ENVIRONMENT != "production" else ["http://localhost:8000", "http://127.0.0.1:8000"]
  handler.add_middleware(CORSMiddleware, allow_origins=allow_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
  This violates decisions/security.md in every non-production environment (wildcard origins + credentials=True) and the "production" branch is a hardcoded localhost list (not real origins) - both branches are environment-derived, which the decision record forbids outright.
- **Additional gap found beyond the original issue text**: allow_methods=["*"] and allow_headers=["*"] are ALSO combined with allow_credentials=True. Per FastAPI's official CORS docs (fetched 2026-07-21): "None of allow_origins, allow_methods and allow_headers can be set to ['*'] if allow_credentials is set to True. All of them must be explicitly specified." docs/adr/api-security.md (historical long-form ADR, superseded by decisions/ but still directionally correct) independently states the same target: explicit methods (GET, POST, PUT, PATCH, DELETE, OPTIONS) and explicit headers (Authorization, Content-Type, X-Request-ID, traceparent). Added as new AC #4 on this task; fixed in the same file/block as the origins fix (no scope-gate impact).
- **Rejected approach - deriving CORS origins from the app's own base URL**: terraform confirms sre-bot.cdssandbox.xyz (terraform/route53.tf, terraform/acm.tf) is this API's OWN domain. CORS exists specifically to authorize a DIFFERENT origin (the calling browser frontend) - same-origin requests never need CORS at all. Reflecting the API's own URL back as an "allowed origin" would be a conceptual error, not a shortcut. Additionally, app/api/routes/landing.py confirms the actual browser frontend "has moved to Backstage" - an external product whose origin does not appear anywhere in this repo (terraform, .env, docs, or settings). The correct default per industry best practice (FastAPI docs, this repo's own AWS_ADMIN_GROUPS-style list-settings convention) is an explicit, deny-by-default empty list, populated with the real Backstage origin once supplied by a human - not derived from anything in app.py.
- SecuritySettings (app/infrastructure/security/settings.py) exists but only owns `jwks`; it is not wired to CORS and TASK-24 (wiring it as the real security settings slice, per docs/adr/api-security.md's target state of "centralized in SecuritySettings") is still To Do. Per the issue's own instruction ("the SecuritySettings slice if task-24 has landed, otherwise app settings"), CORS_ALLOWED_ORIGINS/METHODS/HEADERS belong on AppSettings (app/infrastructure/configuration/app.py) as an interim home for this task, to be migrated to SecuritySettings when TASK-24 lands.
- Boot-time validator idiom already established in this codebase: `@model_validator(mode="after")` raising `ValueError` on invalid state (see app/integrations/slack/settings.py SlackSettings._validate_transport_credentials, app/infrastructure/configuration/infrastructure/platforms.py SlackPlatformSettings._validate_config). Reuse this pattern instead of inventing a lifespan-phase check - it fires at AppSettings() construction time, which is effectively process boot since server.py calls get_app_settings() at module import.
- list[str] settings fields already exist and are populated from env (e.g. AWS_ADMIN_GROUPS in app/infrastructure/configuration/features/aws_ops.py) - same field-typing convention applies to the new CORS fields.
- Deployment config: only one environment is deployed via IaC in this repo - terraform/ecs.tf (template vars) + terraform/templates/sre-bot.json.tpl (ECS container `environment` array), currently carrying BACKEND_URL and ENVIRONMENT=production. Non-production environments (local/dev/ci/staging) are developer-run via .env, not terraform. DoD#2 ("per-environment origin lists set in deployment config") maps to adding a CORS_ALLOWED_ORIGINS entry to this one production template plus a new terraform variable. CORS_ALLOWED_METHODS/HEADERS do NOT need per-environment terraform values - they are a fixed security policy (not deployment-varying), so safe non-wildcard defaults baked into AppSettings are sufficient; no terraform change needed for those two.
- Dependency check: TASK-2 depends on TASK-1. The TASK-1 container and TASK-1.2 container still show "To Do", but the subtasks that actually deliver the ENVIRONMENT field and migrate CORS off PREFIX (TASK-1.1, TASK-1.2.1, TASK-1.2.2, TASK-1.2.3) are all Done, and app.py/server.py already reflect that migration. TASK-2 is unblocked at the code level; the parent containers are bookkeeping only.

## Implementation steps

1. app/infrastructure/configuration/app.py (AppSettings):
   - Add `CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list, alias="CORS_ALLOWED_ORIGINS")` - default empty list (secure-by-default: no origins allowed until explicitly configured), not a wildcard.
   - Add `CORS_ALLOWED_METHODS: list[str] = Field(default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], alias="CORS_ALLOWED_METHODS")` and `CORS_ALLOWED_HEADERS: list[str] = Field(default=["Authorization", "Content-Type", "X-Request-ID", "traceparent"], alias="CORS_ALLOWED_HEADERS")`, matching docs/adr/api-security.md's stated policy set.
   - Add `from pydantic import Field, model_validator` and a `@model_validator(mode="after")` method that raises `ValueError(...)` referencing decisions/security.md SEC-1 when `"*"` appears in ANY of CORS_ALLOWED_ORIGINS, CORS_ALLOWED_METHODS, or CORS_ALLOWED_HEADERS (this server always sets allow_credentials=True, so wildcard is forbidden in all three per FastAPI/Starlette's own constraint).
   - Update class docstring/Environment Variables list to document all three new fields and note they are an interim AppSettings home pending TASK-24's SecuritySettings migration.

2. app/server/server.py:
   - Delete the `allow_origins = (...)` ENVIRONMENT-derived block (lines ~21-28).
   - Pass `allow_origins=app_settings.CORS_ALLOWED_ORIGINS`, `allow_methods=app_settings.CORS_ALLOWED_METHODS`, `allow_headers=app_settings.CORS_ALLOWED_HEADERS` directly to `CORSMiddleware(...)`.
   - No environment/PREFIX conditional remains in this file for CORS.

3. Tests:
   - app/tests/unit/infrastructure/configuration/test_app_settings.py: add a `TestAppSettingsCors` covering: origins/methods/headers defaults (empty origins; non-empty safe method/header defaults); explicit non-wildcard values round-trip; constructing with `"*"` in CORS_ALLOWED_ORIGINS, CORS_ALLOWED_METHODS, or CORS_ALLOWED_HEADERS (each independently, plus one mixed-list case e.g. `["*", "https://example.com"]`) raises `ValidationError` wrapping the model validator's ValueError, consistent with the existing `test_environment_invalid_value_raises_validation_error` pattern.
   - app/tests/unit/server/test_server.py: extend `test_cors_middleware_configured` to assert the CORSMiddleware's `allow_origins`/`allow_methods`/`allow_headers` kwargs equal `app_settings.CORS_ALLOWED_ORIGINS/METHODS/HEADERS` (inspect `app.user_middleware` entries' `.kwargs`) and contain no `"*"`. Add a reload-based test following the existing `importlib.reload` pattern in app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py: monkeypatch `infrastructure.configuration.app.get_app_settings` to return an AppSettings with a specific CORS_ALLOWED_ORIGINS list, `importlib.reload(server)`, and assert the middleware reflects that exact list - proving the value flows from settings, not from ENVIRONMENT branching.
   - app/tests/integration/server/test_server_integration.py: keep the existing CORSMiddleware-presence assertion; optionally add an assertion that no `"*"` appears in the configured origins/methods/headers.

4. Deployment config (terraform):
   - terraform/variables.tf: add `variable "cors_allowed_origins" { description = "JSON-encoded list of allowed CORS origins for the production sre-bot API (the real browser-facing frontend origin, e.g. the Backstage instance URL - NOT this API's own domain)"; type = list(string) }`.
   - terraform/ecs.tf: add `cors_allowed_origins = jsonencode(var.cors_allowed_origins)` to the `data "template_file" "sre-bot"` vars block.
   - terraform/templates/sre-bot.json.tpl: add a `{"name": "CORS_ALLOWED_ORIGINS", "value": "${cors_allowed_origins}"}` entry to the `environment` array, alongside `BACKEND_URL`/`ENVIRONMENT`.
   - CORS_ALLOWED_METHODS/HEADERS: no terraform change needed; AppSettings defaults (step 1) already satisfy the policy without per-environment overrides.
   - **Open question for reviewer, unresolved by design**: the real production browser origin (Backstage instance URL) is not present anywhere in this repo's code, terraform, or docs, and reflecting the API's own domain (sre-bot.cdssandbox.xyz) would be incorrect (see Research summary). The human reviewer must supply the actual Backstage origin before this step can be completed. Until then, this step lands with the wiring in place and a required-no-default terraform variable, so misconfiguration fails `terraform apply` rather than silently deploying an empty or wrong allow-list.

## AC / DoD traceability

- AC1 (CORSMiddleware receives explicit origin list; no wildcard logic in server.py) -> Steps 1, 2, 3 (test_server.py assertion).
- AC2 (Boot fails with clear error when "*" + credentials configured; test exists) -> Step 1 (validator) + Step 3 (test_app_settings.py new tests).
- AC3 (grep confirms allow_origins never computed from ENVIRONMENT/PREFIX conditionals) -> Step 2; verify via `grep -n "ENVIRONMENT\|PREFIX" app/server/server.py` returning no allow_origins-related lines.
- AC4 (allow_methods/allow_headers explicit, no wildcard, matching credentials=True) -> Steps 1, 2, 3 (test_server.py + test_app_settings.py validator tests) - added during planning research, not in the original issue text.
- DoD1 (tests pass; new boot-validator test included) -> Step 3.
- DoD2 (per-environment origin lists set in deployment config) -> Step 4; blocked on reviewer-supplied real Backstage origin value (see open question). Methods/headers need no deployment-config change (fixed policy, safe defaults).
- DoD3 (PR references SEC-1 and decisions/security.md) -> PR description, human-authored at submission time.

## Size estimate / single-PR gate

Files touched: app/infrastructure/configuration/app.py, app/server/server.py, app/tests/unit/infrastructure/configuration/test_app_settings.py, app/tests/unit/server/test_server.py, app/tests/integration/server/test_server_integration.py (optional), terraform/variables.tf, terraform/ecs.tf, terraform/templates/sre-bot.json.tpl - 8 files, single subsystem (settings + CORS wiring + its deployment config), estimated ~130-170 production/test LOC changed (slightly larger than the origins-only estimate due to methods/headers fields, still well under the ~400 LOC / ~10 files / multiple-subsystems gate). Verdict: fits in one PR - no decomposition required.

## Assumptions / open questions for human reviewer

1. Real production CORS origin value (the Backstage frontend's URL) is unknown to the agent and must be supplied by the reviewer/team before terraform step 4 can be finalized. It is NOT this API's own domain (sre-bot.cdssandbox.xyz) - deriving it from the app's own base URL would be a CORS misunderstanding, not a valid default. Proposal: land steps 1-3 (code + tests) and the terraform wiring with a required-no-default variable, then populate the actual value in a follow-up commit/PR comment once known - keeps the code-level security fix unblocked by an operational detail.
2. terraform variable type for `cors_allowed_origins` (list(string) vs. a single JSON/comma-separated string) is a minor convention choice; defaulting to `list(string)` + `jsonencode()` for the container env var, consistent with how AppSettings will parse it (pydantic-settings parses JSON-array-shaped env values into list[str] fields by default, same as AWS_ADMIN_GROUPS).
3. CORS_ALLOWED_METHODS/HEADERS default values are taken from docs/adr/api-security.md's stated policy (GET/POST/PUT/PATCH/DELETE/OPTIONS; Authorization/Content-Type/X-Request-ID/traceparent). If the actual route surface uses a narrower or wider set, the reviewer should adjust the defaults - this is a judgment call made during planning, not verified against every route's actual methods.
4. TASK-1/TASK-1.2 parent containers still show "To Do" despite their relevant subtasks (TASK-1.1, 1.2.1, 1.2.2, 1.2.3) being Done; treated as non-blocking bookkeeping since the code prerequisite (ENVIRONMENT field, CORS already reading ENVIRONMENT not PREFIX) is verified present.
5. CORS_ALLOWED_ORIGINS/METHODS/HEADERS are placed on AppSettings as an interim home. When TASK-24 lands SecuritySettings, these three fields (and their validator) should move there - flagged in the AppSettings docstring so it isn't forgotten.

## Blast radius / rollback

- Blast radius: server.py CORS middleware wiring and AppSettings only; no route/business-logic changes. Any consumer currently relying on the wildcard-during-non-production behavior (e.g. local dev tooling hitting the API cross-origin from an arbitrary port) will need its origin added to CORS_ALLOWED_ORIGINS (default `[]` means CORS is fully locked down until configured) - expected and desired per decisions/security.md, but worth calling out in the PR description as a behavior change for local/dev workflows.
- Rollback: revert the single commit/PR; no data migration, no schema change, no irreversible deployment state.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; new boot-validator test included
- [ ] #2 Per-environment origin lists set in deployment config
- [ ] #3 PR references SEC-1 and decisions/security.md
<!-- DOD:END -->
