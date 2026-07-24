---
id: TASK-2
title: 'Fix production CORS: explicit origin allow-list with boot-time validator'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 13:34'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; new boot-validator test included
- [ ] #2 Per-environment origin lists set in deployment config
- [ ] #3 PR references SEC-1 and decisions/security.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Research summary (refreshed 2026-07-24)

- Re-verified against current main (HEAD 832ea553, 'Feat/slack prefix teardown #1339'): TASK-1 and TASK-45 (and all their subtasks) are now Done. AppSettings.PREFIX has been fully deleted from app/infrastructure/configuration/app.py - confirmed by reading the file (only ENVIRONMENT, DEV_BYPASS_ENABLED, LOG_LEVEL, GIT_SHA remain) and by the passing test test_app_settings_no_legacy_prefix_attribute (asserts not hasattr(settings, 'PREFIX')). Slack command namespacing now uses the dedicated SLACK__COMMAND_PREFIX setting (app/infrastructure/slack/settings.py), wired through app/integrations/slack/provider.py and each modules/<x>.py command registration - fully independent of AppSettings and irrelevant to CORS. terraform/templates/sre-bot.json.tpl already carries SLACK__COMMAND_PREFIX (empty value) instead of any PREFIX-derived value. This removes the prior plan's open assumption about TASK-1/TASK-1.2 parent containers - they are Done, not just their subtasks.
- Net effect on this task: none of the CORS wiring depends on PREFIX at all (confirmed unchanged: app/server/server.py:21-28 still does allow_origins = ["*"] if app_settings.ENVIRONMENT != "production" else [hardcoded localhost list], with allow_credentials=True, allow_methods=["*"], allow_headers=["*"] at add_middleware(...)). The AppSettings docstring/description language planned for step 1 no longer needs any 'interim PREFIX-adjacent' framing since PREFIX is simply gone - just document the three new CORS_ALLOWED_* fields plainly.
- decisions/security.md (CORS clause) and docs/adr/api-security.md (target SecuritySettings shape, explicit method/header set: GET/POST/PUT/PATCH/DELETE/OPTIONS; Authorization/Content-Type/X-Request-ID/traceparent) re-read and unchanged from prior research; still the binding source for defaults and the boot-validator requirement.
- app/infrastructure/security/settings.py (SecuritySettings) re-read: still only owns jwks (JWKSSettings); CORS/rate-limit/dev-bypass fields are commented-out placeholders. TASK-24 (still To Do) is confirmed NOT landed, matching the user's explicit direction: build CORS_ALLOWED_ORIGINS/METHODS/HEADERS + boot validator on AppSettings now (interim home), and separately annotate TASK-24 (via --comment, done in this planning session) that it must migrate these three fields and the validator into SecuritySettings when it lands, rather than re-deriving them from scratch.
- terraform/variables.tf, terraform/ecs.tf, terraform/templates/sre-bot.json.tpl re-read: no existing cors_allowed_origins variable/wiring; single deployed environment (production) via ECS; non-prod environments remain developer-run via .env. Plan for deployment config (step 4) is unchanged from prior research.
- Test scaffolding re-confirmed present and matching planned edit points: app/tests/unit/infrastructure/configuration/test_app_settings.py (TestAppSettings, TestAppSettingsEnvironment classes; test_environment_invalid_value_raises_validation_error is the pattern to mirror for the new CORS validator tests), app/tests/unit/server/test_server.py (test_cors_middleware_configured is the extension point), app/tests/integration/server/test_server_integration.py (test_server_has_cors_middleware_configured is the extension point), app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py (importlib.reload(dynamodb_module) pattern at line 41, to mirror for the server-reload CORS test).

## Implementation steps

1. app/infrastructure/configuration/app.py (AppSettings):
   - Add CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list, alias='CORS_ALLOWED_ORIGINS') - default empty list (secure-by-default: no origins allowed until explicitly configured).
   - Add CORS_ALLOWED_METHODS: list[str] = Field(default=['GET','POST','PUT','PATCH','DELETE','OPTIONS'], alias='CORS_ALLOWED_METHODS') and CORS_ALLOWED_HEADERS: list[str] = Field(default=['Authorization','Content-Type','X-Request-ID','traceparent'], alias='CORS_ALLOWED_HEADERS'), matching docs/adr/api-security.md's stated policy set.
   - Import model_validator from pydantic; add a @model_validator(mode='after') that raises ValueError (referencing decisions/security.md SEC-1 / CORS clause) when '*' appears in ANY of CORS_ALLOWED_ORIGINS, CORS_ALLOWED_METHODS, or CORS_ALLOWED_HEADERS, since this server always sets allow_credentials=True.
   - Update the class docstring to document the three new fields as the CORS allow-list policy, noting they are an interim AppSettings home pending TASK-24's SecuritySettings migration (no PREFIX-related wording needed - that setting is already fully removed).

2. app/server/server.py:
   - Delete the allow_origins = (...) ENVIRONMENT-derived ternary block (current lines ~21-28).
   - Pass allow_origins=app_settings.CORS_ALLOWED_ORIGINS, allow_methods=app_settings.CORS_ALLOWED_METHODS, allow_headers=app_settings.CORS_ALLOWED_HEADERS directly into CORSMiddleware(...) alongside the existing allow_credentials=True.
   - No ENVIRONMENT/PREFIX conditional remains in this file for CORS.

3. Tests:
   - app/tests/unit/infrastructure/configuration/test_app_settings.py: add a TestAppSettingsCors class covering: defaults (empty origins list; non-empty safe method/header defaults); explicit non-wildcard values round-trip; constructing with '*' in CORS_ALLOWED_ORIGINS, CORS_ALLOWED_METHODS, or CORS_ALLOWED_HEADERS (each independently, plus one mixed-list case e.g. ['*','https://example.com']) raises ValidationError wrapping the model validator's ValueError - mirroring test_environment_invalid_value_raises_validation_error.
   - app/tests/unit/server/test_server.py: extend test_cors_middleware_configured to assert the CORSMiddleware entry's kwargs for allow_origins/allow_methods/allow_headers equal app_settings.CORS_ALLOWED_ORIGINS/METHODS/HEADERS (via app.user_middleware entries' .kwargs) and contain no '*'. Add a reload-based test mirroring importlib.reload pattern in test_dynamodb_local_endpoint.py: monkeypatch infrastructure.configuration.app.get_app_settings to return an AppSettings with a specific CORS_ALLOWED_ORIGINS list, importlib.reload(server), assert the middleware reflects that exact list - proving the value flows from settings, not from ENVIRONMENT branching.
   - app/tests/integration/server/test_server_integration.py: keep test_server_has_cors_middleware_configured; add an assertion that no '*' appears in the configured origins/methods/headers.

4. Deployment config (terraform):
   - terraform/variables.tf: add variable "cors_allowed_origins" { description = "JSON-encoded list of allowed CORS origins for the production sre-bot API (the real browser-facing frontend origin, e.g. the Backstage instance URL - NOT this API's own domain)"; type = list(string) } (no default - required, so misconfiguration fails terraform apply rather than silently deploying empty/wrong allow-list).
   - terraform/ecs.tf: add cors_allowed_origins = jsonencode(var.cors_allowed_origins) to the data "template_file" "sre-bot" vars block.
   - terraform/templates/sre-bot.json.tpl: add {"name": "CORS_ALLOWED_ORIGINS", "value": "${cors_allowed_origins}"} to the environment array, alongside BACKEND_URL/ENVIRONMENT/SLACK__COMMAND_PREFIX.
   - CORS_ALLOWED_METHODS/HEADERS: no terraform change needed; AppSettings defaults (step 1) already satisfy the fixed security policy without per-environment overrides.
   - Open question for reviewer, unresolved by design: the real production browser origin (Backstage instance URL) is not present anywhere in this repo. Proposal: land steps 1-3 (code + tests) and the terraform wiring with a required-no-default variable; populate the actual value once known.

## AC / DoD traceability

- AC1 (CORSMiddleware receives explicit origin list; no wildcard logic in server.py) -> Steps 1, 2; verified by test_server.py assertions.
- AC2 (Boot fails with clear error when '*' + credentials configured; test exists) -> Step 1 (validator) + Step 3 (test_app_settings.py new tests).
- AC3 (grep: allow_origins never computed from ENVIRONMENT/PREFIX conditionals) -> Step 2; verify via grep -n 'ENVIRONMENT|PREFIX' app/server/server.py returning no allow_origins-related lines.
- AC4 (allow_methods/allow_headers explicit, no wildcard, matching credentials=True) -> Steps 1, 2, 3.
- DoD1 (tests pass; new boot-validator test included) -> Step 3.
- DoD2 (per-environment origin lists set in deployment config) -> Step 4; blocked on reviewer-supplied real Backstage origin value. Methods/headers need no deployment-config change.
- DoD3 (PR references SEC-1 and decisions/security.md) -> PR description, human-authored at submission time.

## Size estimate / single-PR gate

Files touched: app/infrastructure/configuration/app.py, app/server/server.py, app/tests/unit/infrastructure/configuration/test_app_settings.py, app/tests/unit/server/test_server.py, app/tests/integration/server/test_server_integration.py, terraform/variables.tf, terraform/ecs.tf, terraform/templates/sre-bot.json.tpl - 8 files, single subsystem (settings + CORS wiring + its deployment config), estimated ~130-170 production/test LOC changed - well under the ~400 LOC / ~10 files / multiple-subsystems gate. Verdict: fits in one PR - no decomposition required.

## Assumptions / open questions for human reviewer

1. Real production CORS origin value (Backstage frontend URL) is unknown to the agent; must be supplied by the reviewer before terraform step 4's variable value can be finalized. Proposal: land steps 1-3 and the terraform wiring with a required-no-default variable now; populate the value in a follow-up once known.
2. terraform variable type: list(string) + jsonencode() for the container env var, consistent with pydantic-settings' JSON-array env parsing (same convention as AWS_ADMIN_GROUPS).
3. CORS_ALLOWED_METHODS/HEADERS defaults taken from docs/adr/api-security.md's stated policy; reviewer should adjust if the actual route surface needs a narrower/wider set.
4. CORS_ALLOWED_ORIGINS/METHODS/HEADERS are placed on AppSettings as an interim home; TASK-24 has been annotated (comment added this session) to migrate these three fields plus their boot validator into SecuritySettings when it lands - not to re-derive the requirement from scratch.
5. Superseded: the prior plan's note about TASK-1/TASK-1.2 parent containers being 'To Do bookkeeping only' no longer applies - TASK-1 and TASK-45 (and all subtasks) are confirmed Done as of 2026-07-24; TASK-2 has no remaining dependency blocker.

## Blast radius / rollback

- Blast radius: server.py CORS middleware wiring and AppSettings only; no route/business-logic changes. Any consumer relying on the current wildcard-during-non-production behavior (e.g. local dev tooling hitting the API cross-origin from an arbitrary port) will need its origin added to CORS_ALLOWED_ORIGINS (default [] locks CORS down until configured) - expected per decisions/security.md, called out as a behavior change in the PR description.
- Rollback: revert the single commit/PR; no data migration, no schema change, no irreversible deployment state.
<!-- SECTION:PLAN:END -->
