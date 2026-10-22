---
id: TASK-111.5.1
title: Lower-case the hosting and security settings fields
status: In Progress
assignee: []
created_date: '2026-10-21T20:23:00Z'
updated_date: '2026-10-21T21:20:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-111.5
type: feature
ordinal: 425000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical, first of two PRs for TASK-111.5. InfrastructureSettings gets case_sensitive=False. The fields of AuditSettings, ConditionalWriteSettings (coordination), SchedulerSettings and SecuritySettings become lower snake_case and every reader follows. Retry, directory, drive and spreadsheets are already lower-case and only inherit case_sensitive=False. Environment names do not change: an alias equal to the upper-cased field name is dropped, an alias that differs is kept (111.8 and 111.13 delete those when they move the slice onto the files). Starting input: the draft slice-1 plan and risks R1 to R8 in TASK-111.5. Must handle infrastructure/coordination/factory.py:18, whose model_copy string key would otherwise silently drop the custom in-progress TTL.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AuditSettings, ConditionalWriteSettings, SchedulerSettings and SecuritySettings declare lower snake_case fields; InfrastructureSettings and SecuritySettings use case_sensitive=False; every slice reads the same environment names as before
- [x] #2 No behaviour change: existing tests pass with attribute renames only, except the SecuritySettings case_sensitive assertion flipping to False and an added regression test that build_conditional_write_store honours its in-progress TTL
- [x] #3 A parametrized test in app/tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py pins every environment name of the touched slices (doc-14 inventory plus deploy-interface names): each name set to a sentinel is received by the renamed field
- [x] #4 No reader in app/, bin/, terraform/ or .github/ uses an old attribute name (rg check recorded in the notes)
- [x] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
- [x] #6 The implementation notes carry the post-deploy checklist (build_and_deploy Slack success, one PRIMARY deployment COMPLETED, no plugin_boot_failed or ERROR in the first minutes of logs, one Slack command in the test channel), the auth checks (security_services_initialized issuer_count equals the pre-deploy baseline with no issuer-config warning; an unauthenticated protected call returns 401, not 500; a CORS preflight is unchanged) and the manual-retag rollback
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.5.1 (hosting + security, mechanical, one PR). Gate: file-count exception approved by the human (comment #3 on 111.5). 14 production files, ~55 changed production LOC, 2 subsystems touched in name only (infrastructure + server), no behaviour change. Not re-split. Line numbers re-verified 2026-10-21.

== Call sites (path:line) ==
Hosting (from the 111.5 draft, re-verified):
- infrastructure/configuration/base.py:~28 InfrastructureSettings.case_sensitive=True -> False (FeatureSettings untouched, 111.14)
- infrastructure/audit/settings.py:17 AUDIT_TABLE_NAME (alias == name); reader infrastructure/audit/service.py:263
- infrastructure/coordination/settings.py:21-24 IDEMPOTENCY_TTL_SECONDS, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS (aliases == names); readers coordination/in_memory.py:26-27, coordination/dynamodb.py:40-41, coordination/factory.py:18 (model_copy string key, R1)
- jobs/settings.py:13-15 DEFAULT_TIER2_LEASE_TTL_SECONDS (alias == name); reader jobs/scheduled_tasks.py:92
- retry, directory, drive, spreadsheets: already lower-case; only inherit case_sensitive=False. No edit.
Security:
- infrastructure/security/settings.py:30-34 model_config (own BaseSettings model_config, NOT InfrastructureSettings; case_sensitive=True -> False); fields :37-44 (ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS, DEV_BYPASS_ENABLED, DEV_BYPASS_TOKEN; no aliases/AliasChoices anywhere); field_validator("ISSUER_CONFIG") :46; model_validator bodies read self.ISSUER_CONFIG :57 and self.CORS_ALLOWED_* :66-68 (the tuple labels "CORS_ALLOWED_ORIGINS" etc. at :66-68 and the messages :59, :72 are env-var text, R5: keep)
- infrastructure/security/jwks.py:21-22 settings.ISSUER_CONFIG (:24 log key="ISSUER_CONFIG" and :27 detail text stay)
- infrastructure/security/current_user.py:101 .DEV_BYPASS_TOKEN, :104 .DEV_BYPASS_ENABLED (docstrings :27,:31,:68-69 are env-var prose, keep). ENVIRONMENT reads at :103,:109 are NOT touched (111.5.2).
- server/server.py:26,29,30 security_settings.CORS_ALLOWED_ORIGINS/METHODS/HEADERS (WEBHOOK_MAX_BODY_BYTES :34 and ENVIRONMENT reads are 111.5.2: do not touch)
- server/lifespan.py:162 settings.ISSUER_CONFIG (:156,:166 text keeps env spelling). :99 logs tuple(security_settings.model_dump().keys()): no edit, but the logged security keys become lower case (R2). lifespan has NO hosting reads. Lines 92-93,97-98,100-101,134,250 are 111.5.2.
- Repo-wide: no getattr/string access, no terraform/.github/bin reader of the attributes (bin/dev-token.py:6-15,183-185 print env-var text only). pyproject.toml:144 sets ISSUER_CONFIG='test-issuer-config' for pytest (env name, unchanged; the slice's before-validator turns the non-object into {}; probed: still {} under case_sensitive=False).
- Probe results (pydantic 2.14, pydantic-settings, case_sensitive=False): (a) lower-case field without alias reads the upper-case env name, incl. JSON dict, JSON list, bool and SecretStr; (b) upper-case constructor kwargs are still accepted; (c) a field_validator naming a missing field ("ISSUER_CONFIG" after the rename) raises PydanticUserError at class creation, so that one cannot go stale silently. model_validator(mode="after") has no string keys, so it only breaks by attribute AttributeError at validation (caught by the tests).

== Ordered steps ==
1. (failing first) Create app/tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py. One parametrized table (settings class, env name, attribute, sentinel text, expected value); monkeypatch.setenv(name, sentinel), build with _env_file=None (fresh instance, not the lru_cache provider), assert getattr(settings, attribute) == expected. Rows:
   Hosting: AUDIT_TABLE_NAME="sentinel_audit"; IDEMPOTENCY_TTL_SECONDS="1234"; IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS="567"; DEFAULT_TIER2_LEASE_TTL_SECONDS="777" (all differ from defaults 3600/300 and scheduler default); RETRY_ENABLED, RETRY_BACKEND, RETRY_DYNAMODB_TABLE_NAME, RETRY_DYNAMODB_TTL_DAYS, RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY_SECONDS, RETRY_MAX_DELAY_SECONDS, RETRY_BATCH_SIZE, RETRY_CLAIM_LEASE_SECONDS, DIRECTORY_PROVIDER, DIRECTORY_REQUIRE_STARTUP_WARMUP, DIRECTORY_CACHE_TTL_SECONDS, DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS, DRIVE_PROVIDER, SPREADSHEET_PROVIDER (read each class's real field/alias names before writing; non-default sentinel of the right type for each).
   Security (SecuritySettings): ISSUER_CONFIG='{"https://issuer.sentinel.example":{"jwks_uri":"https://issuer.sentinel.example/jwks","algorithms":["ES256"],"audience":"sentinel-audience"}}' expect equal dict (default None, so it differs; it carries the required audience so the model validator passes); CORS_ALLOWED_ORIGINS='["https://sentinel.example"]' (default []); CORS_ALLOWED_METHODS='["PUT"]' (default GET,POST); CORS_ALLOWED_HEADERS='["X-Sentinel"]' (default Authorization,...); DEV_BYPASS_ENABLED="true" (default False); DEV_BYPASS_TOKEN="sentinel-token" compare .get_secret_value() (default None). Plus one row/test for the live production form CORS_ALLOWED_ORIGINS="[]" -> [] (jsonencode of the empty terraform default) so the real deployed value parses.
   Additional tests in the same file: lower-case env name (e.g. audit_table_name) accepted; upper-case constructor kwarg accepted (A1); docstring states hosting names are not set in production, ISSUER_CONFIG and CORS_ALLOWED_ORIGINS are. Run it: the renamed-attribute rows fail (AttributeError) until steps 2-6; this is the red state. No task ids in docstrings.
2. infrastructure/configuration/base.py: InfrastructureSettings case_sensitive=False.
3. infrastructure/audit/settings.py -> audit_table_name, drop alias; infrastructure/audit/service.py:263 reader.
4. infrastructure/coordination/settings.py -> idempotency_ttl_seconds, idempotency_in_progress_ttl_seconds, drop aliases; readers in_memory.py:26-27, dynamodb.py:40-41, factory.py:18 (update key becomes "idempotency_in_progress_ttl_seconds"; R1: model_copy does not validate, so the old key would silently ignore the custom TTL).
5. jobs/settings.py -> default_tier2_lease_ttl_seconds, drop alias; jobs/scheduled_tasks.py:92 reader.
6. infrastructure/security/settings.py: model_config case_sensitive=False (keep own BaseSettings base, env_file, extra="ignore"; do not switch to InfrastructureSettings, 111.8 changes the base); rename the 6 fields to lower snake_case, no alias added; field_validator("issuer_config"); model_validator bodies read self.issuer_config / self.cors_allowed_*; the tuple labels and ValueError messages keep ISSUER_CONFIG / CORS_ALLOWED_* spelling (R5). Update the class docstring only if needed (env-var names listed stay).
7. Security readers: jwks.py:21-22; current_user.py:101,104; server/server.py:26,29,30; server/lifespan.py:162. Nothing else in those files.
8. Existing tests, attribute renames only (constructor kwargs/setenv names stay upper case):
   - tests/unit/infrastructure/security/test_security_settings_load.py: attribute reads to lower case (35 refs; kwargs and setenv names unchanged); the case_sensitive assertion at :127-132 flips to False and its name/docstring says "case-insensitively"; _NAMES (:~22-29) used at the end as `name in SecuritySettings.model_fields` / AppSettings.model_fields becomes name.lower().
   - tests/unit/server/test_server.py:42-44 (attribute reads); :58-60,:84 kwargs stay.
   - tests/integration/server/test_lifespan_security_settings_validation.py:103 (.cors_allowed_origins); env names and match= strings stay.
   - tests/integration/server/test_lifespan.py:79,101: MagicMock model_dump keys to lower case (fidelity only: the mock would hide a mismatch; keep the LOG_LEVEL/GIT_SHA label assertion at :99 untouched, that is 111.5.2).
   - tests/unit/infrastructure/security/test_current_user_bypass.py, test_security_jwks_issuer_config.py: kwargs only; verify no attribute reads need change.
   - Hosting tests per the draft: tests/unit/infrastructure/coordination/{test_coordination_settings.py, test_coordination_dynamodb_store_operations.py:34-35, test_coordination_in_memory_store_operations.py, test_coordination_dynamodb_ownership.py, test_coordination_run_if_leased.py}, tests/integration/infrastructure/coordination/conftest.py (Mock attrs), tests/unit/infrastructure/audit/test_audit_settings_table_name.py, tests/unit/jobs/{test_jobs_settings.py, test_scheduled_tasks.py:321,353,415 (Mock attrs)}. Untouched on purpose (kwargs or dict-key labels only): tests/fixtures/service_registry.py:32, tests/unit/contracts/coordination/conftest.py:39,46, tests/unit/packages/access/sync/*, tests/conftest.py:426, tests/integration/conftest.py:130.
   - Add R1 regression to tests/unit/infrastructure/coordination/test_coordination_store_factory.py: build_conditional_write_store(..., in_progress_ttl_seconds=N) yields a store whose in-progress TTL is N, not the base 300.
9. Gates from /workspace/app: uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files; confirm the pydantic mypy plugin accepts upper-case kwargs in tests, since SecuritySettings has extra="ignore" the generated __init__ keeps **kwargs); uv run pytest tests --ignore=tests/smoke; make check-import-contracts; make check-settings-key-ownership (case-folded, ownership unchanged, test_bin_settings_key_ownership_check.py:549 re-derives SecuritySettings against pydantic and must still pass).
10. AC4 sweep, recorded in notes: rg -n '\.(AUDIT_TABLE_NAME|IDEMPOTENCY_TTL_SECONDS|IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS|DEFAULT_TIER2_LEASE_TTL_SECONDS|ISSUER_CONFIG|CORS_ALLOWED_(ORIGINS|METHODS|HEADERS)|DEV_BYPASS_(ENABLED|TOKEN))\b' and the quoted model_copy/getattr forms over app/ bin/ terraform/ .github/ returns only env-var strings, docstrings, log labels, kwargs and the pin table.
11. Final --notes: file list, test counts, rg output, post-deploy checklist and rollback below.

== AC -> step -> test (and back) ==
AC1 -> steps 2-7 -> pin test rows (hosting + security), test_security_settings_load (case-insensitive config), existing coordination/audit/jobs settings tests.
AC2 -> step 8 (renames only) + the two named exceptions: security case_sensitive flip (test_security_settings_load.py ~127) and R1 regression (test_coordination_store_factory.py).
AC3 -> step 1 -> test_configuration_settings_production_names.py (written first, red, then green).
AC4 -> step 10 rg sweep.
AC5 -> step 9.
AC6 -> step 11 (notes).
Reverse: steps 2-7 -> AC1; 8 -> AC2; 1 -> AC3; 9 -> AC5; 10 -> AC4; 11 -> AC6. No unmapped step.

== Test matrix ==
Happy: each env name -> renamed field (pin table, hosting + security). Default: unset env keeps defaults (existing slice tests). Boundary: lower-case env name accepted; upper-case kwarg accepted; CORS "[]" parses empty; ISSUER_CONFIG non-object text -> {} (existing). Failure: CORS wildcard in each list and issuer without audience still raise ValidationError naming the env spelling (existing test_security_settings_load.py, lifespan boot-fail tests); invalid int for idempotency TTL raises. Regression: R1 factory TTL. Authorization: current_user dev-bypass tests (enabled+token, flag off, token missing, production denied) pass unchanged: they are the guard that the renamed bypass attributes are really read. Idempotency: coordination store tests unchanged.
Files: tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py (new), plus the edits above.

== Validation against ADRs and 111.8 ==
decisions/configuration.md: lower snake_case fields equal TOML keys, no per-field aliases as end state; this PR removes aliases that merely equal the name and adds none. decisions/security.md: no CORS wildcard, dev bypass two guards (ENVIRONMENT != production AND flag) both preserved; messages unchanged. Settings partitioning respected (no growth of aggregators; SecuritySettings stays in its slice). No import-boundary change. 111.8 (security onto ConfigurationSlice, env_prefix SECURITY__, extra=forbid) needs field names == TOML keys issuer_config, cors_allowed_*, dev_bypass_enabled, dev_bypass_token: exactly what lands here, and no alias exists to delete, so 111.8 reverts nothing. Only the base class and model_config are 111.8's to change. 111.13 likewise: the hosting fields already equal the keys.

== Assumptions (verify) ==
A1 Upper-case constructor kwargs stay valid under case_sensitive=False: probed; the pin file asserts it explicitly. If it fails, rename kwargs in tests (no prod change).
A2 Production sets ISSUER_CONFIG (SSM-delivered .env via entry.sh, JSON) and CORS_ALLOWED_ORIGINS (task definition, jsonencode of the empty list); nothing else here (doc-14 lines 22-24, 94). DEV_BYPASS_* , CORS methods/headers, hosting names are on defaults/not set. Verify with aws ecs describe-task-definition (environment names) and the .env keys before merge.
A3 .env keys from entry.sh match case-insensitively under case_sensitive=False (dotenv source lower-cases): pinned by an extra pin-test case that writes a tmp .env via _env_file.
A4 The pydantic mypy plugin keeps accepting upper-case kwargs: confirmed by the mypy gate in step 9.
A5 No CloudWatch metric filter/alarm keys on configuration_loaded key names (security keys now log lower case, R2): rg terraform for aws_cloudwatch_log_metric_filter / configuration_loaded before merge.
A6 No log consumer or doc generator depends on field names (R8): none found.
A7 Field-level ValidationError locations now show lower-case field names (env var is the same name case-insensitively); custom messages still use env spelling. Accepted.

== Blast radius and rollback ==
Merging to main deploys. No ECS deployment circuit breaker and the :latest image until TASK-111.16, so nothing rolls back automatically. Failure modes: (1) hosting: boot-time AttributeError in audit/coordination/scheduler wiring (loud, new task fails to stabilise) or R1 (silently wrong lease TTL, caught by the new regression test). (2) SECURITY, higher risk and quiet: a missed or mismatched issuer_config read leaves lifespan in its degraded mode (warning only, boot succeeds, /health static) and every authenticated request fails; a broken CORS read changes browser access without failing boot; a flipped bypass read could only fail closed. The pin test, validators tests and bypass tests are the CI guard; the checks below are the production guard. Rollback: one git revert restores code but needs a merge+deploy; faster is the manual retag of the previous <sha>-<date> image as latest and forcing a new ECS deployment. No terraform/env change, so no ordering constraint; ship alone, before 111.8.

== Post-deploy checklist (also goes in the implementation notes) ==
Before merge, record baseline from current prod logs: the security_services_initialized issuer_count value.
1. build_and_deploy posts its Slack success message.
2. aws ecs describe-services shows exactly one PRIMARY deployment, rolloutState COMPLETED.
3. CloudWatch sre-bot logs after the new task starts: no plugin_boot_failed, no ERROR level.
4. One Slack command in the test channel responds.
5. Auth-specific (security half): logs show security_services_initialized with issuer_count equal to the baseline, and NO security_services_no_issuer_config or issuer_config_not_set warning. configuration_loaded security keys now log lower case (expected).
6. Auth-specific: an unauthenticated call to an authenticated API route returns 401 with WWW-Authenticate (not 500 and not 200); if a valid Backstage/service token is available, one authenticated call succeeds.
7. CORS: an OPTIONS preflight from an arbitrary Origin gets no Access-Control-Allow-Origin (production origins are empty), same as before the deploy.
Rollback on any failure: manual retag of the previous <sha>-<date> image.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-21. 14 production files, no behaviour change; environment names unchanged.

Production files: infrastructure/configuration/base.py (InfrastructureSettings case_sensitive=False; FeatureSettings untouched), infrastructure/audit/{settings,service}.py, infrastructure/coordination/{settings,in_memory,dynamodb,factory}.py, jobs/{settings,scheduled_tasks}.py, infrastructure/security/{settings,jwks,current_user}.py, server/{server,lifespan}.py. Aliases equal to the field name dropped (audit, coordination, scheduler); SecuritySettings had none and keeps its own BaseSettings base for 111.8. Validator messages, log labels and docstrings keep the environment spelling.

R1: coordination/factory.py:18 model_copy key renamed. The existing tests test_build_conditional_write_store_overrides_in_progress_ttl_only and test_build_lease_store_wraps_a_dynamodb_store_with_the_lease_ttl already guard it: with every rename but this one they failed (in-progress TTL 30 instead of 14400), so no extra regression test was added.

Found during implementation: the base flip also makes DirectorySettings.startup_preload_groups (no alias) read STARTUP_PRELOAD_GROUPS in any case; it read only the lower-case name before. Nothing sets either name (rg over the repo, terraform and workflows), so no effect. ServerSettings/DevSettings inherit the flip too; their upper-case fields read the same names (renamed in 111.5.2).

Tests: new tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py (29 cases: every hosting and security name set to a non-default sentinel reaches its field; DRIVE_PROVIDER/SPREADSHEET_PROVIDER proven read by rejecting an unknown value; production CORS "[]" parses; ISSUER_CONFIG from a .env file; lower-case env name and upper-case keyword accepted). Red first (14 failed), green after. Existing tests: attribute renames only, plus test_security_settings_load case_sensitive assertion flipped to False and the test_lifespan mock model_dump keys lower-cased.

Gates (from app/): ruff check . -> All checks passed; pytest tests --ignore=tests/smoke -> 5531 passed; mypy -> 47 errors in 18 files, none in a touched file (pre-existing: modules/incident, modules/webhooks, infrastructure/i18n, resilience, docs_generator, ...); make check-import-contracts -> 12 kept, 0 broken; make check-settings-key-ownership -> OK.

AC4 sweep: rg for the old attribute names (.NAME and model_copy/dict string keys) over app/ bin/ terraform/ .github/ returns only tests/conftest.py:426 and tests/integration/conftest.py:130, both "idempotency.IDEMPOTENCY_TTL_SECONDS" dictionary labels, not attribute access.

Before merge (human): record the production baseline: issuer_count on the latest security_services_initialized line in CloudWatch /ecs/sre-bot-app.

Post-deploy checklist (merging to main deploys; no circuit breaker, :latest until TASK-111.16):
1. build_and_deploy posts its Slack success message.
2. aws ecs describe-services shows exactly one PRIMARY deployment, rolloutState COMPLETED.
3. /ecs/sre-bot-app after the new task starts: no plugin_boot_failed and no ERROR level in the first minutes.
4. One Slack command in the test channel responds.
5. Auth: security_services_initialized issuer_count equals the baseline; no security_services_no_issuer_config or issuer_config_not_set warning. configuration_loaded security keys now log lower case (expected).
6. Auth: an unauthenticated call to a protected API route returns 401 with WWW-Authenticate, not 500.
7. CORS: an OPTIONS preflight from an arbitrary Origin gets no Access-Control-Allow-Origin, as before.
Rollback on any failure: retag the previous <sha>-<date> image as latest and force a new ECS deployment; then revert the merge.

Post-deploy, 2026-10-21 (human): deploy succeeded and new tasks run (checks 1-4). Check 7 passed: OPTIONS preflight from https://example.com to /version returned no Access-Control-Allow-Origin. Check 5 inconclusive: filter-log-events over /ecs/sre-bot-app for the last 24 h found neither security_services_initialized nor the issuer warnings; re-check with aws logs tail. Check 6 not run (no confirmed protected production route).

Post-deploy follow-up 2026-10-21: build_and_deploy run 39674879551 (416a225f) deployed (Restart ECS, Wait for ECS Stability and Slack success all passed at ~21:09 UTC) and then failed only at the post-deploy Docker generate SBOM step (public.ecr.aws trivy-db TOOMANYREQUESTS, unrelated to the change). Baseline issuer_count=1 from the 18:42 UTC boot (previous deploy 1a5f6ab7). aws logs tail --since 3h with filter "security_services" showed only that 18:42 boot; no security_services line from the ~21:0x boot yet: check 5 still open.

Check 5 passed 2026-10-21 (human-run): both new tasks (started 21:01 UTC, digest sha256:30b570f6..., tag 416a225f-2026-10-21 = :latest) logged security_services_initialized with issuer_count=1, equal to the baseline; no security_services_no_issuer_config, issuer_config_not_set or plugin_boot_failed. Warnings/errors in the 2 h after deploy: legacy_api_endpoint_accessed x38 (traffic), access_sync/requests/catalog_disabled x2 each and the slack-bolt 'token will be unused' notice x2 (one per task boot); none relates to a renamed field. Checks 1-5 and 7 passed; check 6 (unauthenticated 401) open or N/A at the human's call.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-21T20:30:00Z

---

Proposal (not applied): extend AC6 so the post-deploy checklist in the notes also carries three auth-specific checks (security_services_initialized issuer_count equals the pre-deploy baseline with no issuer-config warning; unauthenticated protected call returns 401 not 500; CORS preflight unchanged), because a broken issuer or CORS read does not fail boot. The plan carries them as checklist items 5-7. Also: ACs 1-5 unchanged.

---

created: 2026-10-21T20:38:00Z

---

Plan approved by the human 2026-10-21 with the recommended answers: (1) AC6 extended with the three auth checks (applied); (2) the human records the production issuer_count baseline before merge; (3) metric filters match only error/exception/warning text (terraform/local.tf), so lower-case configuration_loaded keys cannot alarm; (4) lower-case field names in ValidationError locations accepted.

---
<!-- COMMENTS:END -->
