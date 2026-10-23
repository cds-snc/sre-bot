---
id: TASK-111.8
title: Move the security slice onto the files
status: In Progress
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-23T15:33:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.5.1
  - TASK-111.16
references:
  - decisions/security.md
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1755
parent_task_id: TASK-111
type: feature
ordinal: 414000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
issuer_config, cors_allowed_origins/methods/headers and dev_bypass_enabled move to [security] in the files (production values from the inventory; production CORS origins are empty today); dev_bypass_token is read as SECURITY__DEV_BYPASS_TOKEN; extra=forbid. Ships and deploys alone because it changes security behaviour inputs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 SecuritySettings reads issuer_config, the CORS lists and dev_bypass_enabled from [security]; production resolves the same values as before
- [x] #2 dev_bypass_token is read only as SECURITY__DEV_BYPASS_TOKEN; base.toml keeps the dev bypass off
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #4 Unknown keys in [security] fail boot naming the file, table and key (extra=forbid), and a wildcard in a CORS list or an issuer without audience still fails boot
- [x] #5 A production pin test asserts the checked-in files resolve the pre-change values (one issuer with audience, empty CORS origins, default methods/headers, dev bypass off, no token) and that no configuration file carries dev_bypass_token
- [x] #6 issuer_config must be a table and each issuer entry is boot-validated (only jwks_uri, algorithms, audience; https jwks_uri or loopback http; algorithms a non-empty asymmetric subset, RS256 when absent); each failure names the issuer and key (Q1)
- [x] #7 create_app refuses to build under ENVIRONMENT=production when dev_bypass_enabled is true or a dev_bypass_token is set, naming the key; security.md and configuration.md:17 amended (Q2)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human: pre-merge gates G1-G8 recorded in the notes (111.7 V1-V8 passed, issuer_config hash match, previous image tag, baseline issuer_count)
- [ ] #2 Human: post-deploy checklist V1-V10 passed
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.8 (security slice onto the configuration files; ONE PR; ships and deploys alone). STATUS: PROPOSED, awaiting human review. Written 2026-10-22 against the TASK-111.7 tree; #1776 merged to main 2026-10-23 (52282a9c). Q1-Q5 reassessed 2026-10-23 against the ADRs and doc-11 (see Decisions assessed). ORDERING: the 111.8 branch is cut from main only after #1776 merges, and 111.8 merges only after the 111.7 deploy passed V1-V8 and its DoD is checked (G1). Re-run every rg below before editing; line numbers are for the reviewer.

== Context ==
SecuritySettings (infrastructure/security/settings.py:16-79) is the last host slice still on BaseSettings with unprefixed env names (ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS, DEV_BYPASS_ENABLED, DEV_BYPASS_TOKEN; env_file .env, extra="ignore"). 111.5.1 already lower-cased the fields to equal the TOML keys with no alias, so only the base class, model_config and values change. 111.7 already builds it in the configuration phase (server/configuration/host_configuration.py:51) and create_app() builds CORS from it (server/server.py:25-36).
Production today (doc-14 lines 22-24, 53, 94; 111.5.1 notes): ISSUER_CONFIG lives only in the SSM blob sre-bot-config, written to .env by entry.sh (baseline issuer_count=1); CORS_ALLOWED_ORIGINS is the task-definition env (terraform var default [] -> "[]", sre-bot.json.tpl:57-58, ecs.tf:34, variables.tf:46); CORS methods/headers and DEV_BYPASS_* are unset (code defaults).
PREMISE CORRECTION: SECURITY__DEV_BYPASS_TOKEN has NO SSM parameter and must not get one: doc-14 line 101 says it and SLACK__SIGNING_SECRET "are not set in production and get no parameter", and terraform/ssm.tf:19-29 lists 11 names without it. The gate is therefore "verify it is absent", not "present". The renamed-secret deploy risk the map attributes to this row does not exist for 111.8 (it reads no SSM SecureString). The only human-supplied production input is the ISSUER_CONFIG value (non-secret: issuer URLs, jwks_uri, algorithms, audience), copied from the blob into production.toml.

== Chosen approach ==
1. SecuritySettings(ConfigurationSlice): model_config toml_table_header=("security",), env_prefix="SECURITY__" (extra=forbid, case-insensitive, .env own-fields-only come from the base). Fields, validators and messages unchanged.
2. app/config/base.toml gains [security]: cors_allowed_origins = [], cors_allowed_methods = ["GET","POST"], cors_allowed_headers = ["Authorization","Content-Type","X-Request-ID","traceparent"], dev_bypass_enabled = false, and an empty [security.issuer_config] (no issuers, as the code default). The base is secure and production-shaped; local.toml, ci.toml and production.toml set no bypass keys (dev bypass stays opt-in per developer through SECURITY__DEV_BYPASS_ENABLED and SECURITY__DEV_BYPASS_TOKEN in app/.env; a flag with no token is inert).
3. AMENDED 2026-10-23 (human): issuers are an array of tables, [[security.issuers]] with issuer, jwks_uri, algorithms, audience, one entry per issuer (any number), because the loader's lower snake_case rule rejects an issuer URL as a table name (verified). The field is issuers: list[IssuerEntry] (frozen, extra=forbid); issuer_config stays as a read-only property keyed by issuer, so jwks.py, jwt.py and the lifespan are unchanged. Env override SECURITY__ISSUERS (JSON list). production.toml gains the production entry, generated from the blob by the human (G4).
4. dev_bypass_token is the only secret: read only as SECURITY__DEV_BYPASS_TOKEN (env or .env), SecretStr, never in any TOML file (test). Not set in production.
5. No change to how readers obtain the slice. Decision (registry vs bridge): the readers of SecuritySettings are jwks.get_issuer_config (jwks.py:20), current_user (current_user.py:99), lifespan._initialize_security_services (lifespan.py:245,275) and create_app (server.py:25). None reads the contracts/configuration.py bridge for settings and none reads at import. They call the cached provider get_security_settings() at call time, or receive the validated object from the configuration phase. That is the tolerated "provider function" form of decisions/dependency-injection.md; HostInfo is the only thing on the registry and on the bridge (current_user.py:100 keeps using host_info() for the environment guard). Registering SecuritySettings in svcs here would be a new pattern for one slice, widen the PR, and TASK-116 (move auth to server/security/) is the owner of moving these readers onto the registry. So: no registry registration, no new bridge field, no new module-level read. 111.9-111.15.2 and TASK-156 are unaffected (156 reads model_dump keys and the bypass/no-issuer flags; field names are unchanged).
6. Dev bypass in production (Q2, proposed): the two per-request guards (current_user.py:103-105) stay. New: create_app() refuses to build when HostInfo.environment == "production" and the slice has dev_bypass_enabled true or a dev_bypass_token set, raising ConfigurationError naming the key (SECURITY__DEV_BYPASS_ENABLED / SECURITY__DEV_BYPASS_TOKEN or [security].dev_bypass_enabled). The check sits in create_app because it joins two slices (identity and security); TASK-116 moves it with the security code. Plus the pins: base/production resolve dev_bypass_enabled False, token None, no file carries dev_bypass_token.
7. Issuer entries are boot-validated (Q1, proposed), in the existing model_validator, keeping the dict type so jwks.py/jwt.py readers are unchanged: issuer_config must be a table (the before-validator's non-object -> {} branch is deleted; absent still means {}); each entry is a table with only the keys jwks_uri, algorithms, audience; jwks_uri is https, or http on a loopback host (127.0.0.1, ::1, localhost; bin/dev-token.py); algorithms, when present, is a non-empty list of names from jwt.py ASYMMETRIC_ALGORITHMS (absent keeps the RS256 default, so the production value is unchanged); audience non-empty. Each failure names the issuer and key. Today an HS* or empty list only logs issuer_no_permitted_algorithms per request and a missing jwks_uri logs issuer_missing_jwks_uri: the issuer is silently unusable.

== Alternatives rejected ==
(a) Split env rename and file move into two PRs: the slice would read two sources with no benefit; one revert is simpler. (b) Keep ISSUER_CONFIG in the SSM blob until 111.15: contradicts the ADR (non-secret value, reviewable) and leaves the blob the only place the production issuer lives. (c) Register SecuritySettings in svcs now: see 5. (d) Boot refusal deferred to TASK-156 as a WARNING: a WARNING leaves a reviewed-config defect running, against lifecycle.md (deploy-coupled defects abort boot). (e) Typed frozen IssuerEntry submodel now: changes every dict reader in jwks.py/jwt.py and their tests; the TASK-116 move is its home (AC added there).

== Readers and old names (verified with rg; app/.env.example unreadable here) ==
Fields: jwks.py:20-22; current_user.py:99-105; lifespan.py:83 (model_dump keys), 135-158; server.py:25-36; host_configuration.py:10,27,51. Old names: pyproject.toml:144 (pytest env ISSUER_CONFIG='test-issuer-config', delete); bin/dev-token.py:6,14,15,183-185 (prints ISSUER_CONFIG snippet; change to SECURITY__ISSUER_CONFIG); current_user.py docstrings :27,:31,:68-69 (env names in prose); jwks.py:24-27 and lifespan.py:140,150 log label/detail text (KEEP: event names and text feed the V checks and any log filters); settings.py validator messages (KEEP). terraform: ecs.tf:34, variables.tf:46, templates/sre-bot.json.tpl:57-58 CORS_ALLOWED_ORIGINS (untouched; unread after the deploy). NOT referenced: .github/workflows, entry.sh, .devcontainer/, app/Makefile, docs/ (rg clean). app/.env.example: could not be read; the implementer reads it, and if still denied the human edits it (see Cleanup). Tests referencing the slice or old names: tests/unit/infrastructure/security/{test_security_settings_load,test_current_user_bypass,test_security_jwks_issuer_config}.py, tests/integration/server/test_lifespan_security_settings_validation.py and test_lifespan.py, tests/unit/server/test_server.py:50-99, tests/unit/bin/test_bin_settings_key_ownership_check.py:555, tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py:86-107,244-288.

== Size gate (verdict: PASSES, no decomposition) ==
Production: 6-7 files (infrastructure/security/settings.py ~45 LOC with the Q1 validator, server/server.py ~10 (Q2), decisions/security.md + configuration.md ~6, app/config/base.toml +~12, production.toml +~10, pyproject.toml -1, bin/dev-token.py ~4, current_user.py docstring ~3) = ~90-110 changed LOC. Tests: ~9 files edited, 1 new. One subsystem (app + checked-in config). Behaviour change only (no mechanical refactor mixed in). One git revert restores service. Reviewable in well under 30 minutes.

== Ordered steps (TDD; run each group red first) ==
S1 Red: tests T1-T7 below (T7 stays red until the G4 value is in production.toml). 
S2 infrastructure/security/settings.py: base class ConfigurationSlice, model_config (toml_table_header, env_prefix), imports; docstring lists SECURITY__ names and [security] keys; fields/validators unchanged.
S3 app/config/base.toml [security] with issuers = []; production.toml [[security.issuers]] (human, G4). T7 green only after G4.
S4 Update existing tests to lower-case kwargs / SECURITY__ names (T8-T11); pyproject.toml drop ISSUER_CONFIG pytest env; bin/dev-token.py snippet; current_user.py docstring prose.
S4a Q1 validator in settings.py (T12 red first); Q2 refusal in server/server.py create_app (T13 red first); ADR edits: security.md Authentication and Dev bypass clauses plus a 2026-10-23 Changes entry, configuration.md:17 (SECURITY__ names, [security] table) and a Changes entry.
S5 Gates (ruff, mypy no new errors vs 47 baseline, pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership). Record rg sweep in notes: rg -n '\b(ISSUER_CONFIG|CORS_ALLOWED_(ORIGINS|METHODS|HEADERS)|DEV_BYPASS_(ENABLED|TOKEN))\b' app bin terraform .github .devcontainer returns only: retired-name tests, log/validator text, docstrings, terraform CORS entries.

== AC -> step -> test ==
AC1 (slice reads [security]; production same values): S2-S3; T1, T2, T7. AC2 (token only as SECURITY__DEV_BYPASS_TOKEN; base bypass off): S2-S3; T3, T4, T7. AC3 (gates): S5. Proposed new AC4 (extra=forbid: unknown key in [security] fails boot naming file/table/key): T5. Proposed new AC5 (production pin: issuer/CORS/bypass equal the pre-change values; no secret in any file): T7. No ADR deviation.

== Test matrix (app/tests, testing-standards names; docstrings describe behaviour only) ==
T1 tests/unit/infrastructure/security/test_security_settings_load.py (edit): table "security", prefix SECURITY__, ConfigurationSlice subclass, extra forbid; defaults come from base.toml (cors [] / GET,POST / default headers / bypass False / token None / issuers {}); SECURITY__CORS_ALLOWED_ORIGINS='["https://a.example"]' beats the file; each field has no alias.
T2 same file: retired unprefixed names (ISSUER_CONFIG, CORS_ALLOWED_*, DEV_BYPASS_ENABLED, DEV_BYPASS_TOKEN) set in the process env and in a .env file are ignored (boundary; this is the behaviour that makes the rollback image the only reader of the blob).
T3 same file: SECURITY__DEV_BYPASS_TOKEN (env and .env) reaches a SecretStr, masked in repr and model_dump_json.
T4 same file: a SECURITY__DEV_BYPASS_TOKEN in the environment does not appear in model_dump keys' values of any log (the lifespan logs key names only); the token's absence from every checked-in file is asserted in T7.
T5 tests/unit/infrastructure/security/test_security_settings_files.py (new): unknown key in a tmp [security] table fails naming the file, table and key (failure); wildcard in each CORS list in a file raises ConfigurationError naming file/table/key; an issuer entry without audience raises; building before install_configuration_files raises.
T6 same file: issuer_config as a TOML table of tables merges base (empty) + environment file key by key (deep merge); a quoted URL key keeps its exact string.
T7 tests/unit/infrastructure/security/test_security_settings_production_values.py (new; the production pin, replaces the security rows of test_configuration_settings_production_names.py): with the real checked-in files and a clean env, production resolves exactly one issuer (baseline issuer_count 1) with https jwks_uri, asymmetric algorithms only (no HS*) and non-empty audience; cors_allowed_origins == [], methods == ["GET","POST"], headers == the default four; dev_bypass_enabled False and dev_bypass_token None for base, ci, local and production; no checked-in file under app/config/ contains the key dev_bypass_token; local/ci resolve no issuers. Authorization case: with SECURITY__DEV_BYPASS_ENABLED=true and the token set under ENVIRONMENT=production the slice builds but test T8 shows the guard refuses.
T8 tests/unit/infrastructure/security/test_current_user_bypass.py (edit): lower-case kwargs (dev_bypass_enabled=, dev_bypass_token=); existing cases kept (enabled+token ok in local, flag off, token missing, production denied even with flag and matching token).
T9 tests/unit/infrastructure/security/test_security_jwks_issuer_config.py (edit): kwargs issuer_config=.
T10 tests/unit/server/test_server.py (edit :50-99) and tests/integration/server/test_lifespan_security_settings_validation.py, test_lifespan.py (edit): build the slice with lower-case kwargs or SECURITY__ env; CORS middleware origin list comes from the slice (a foreign Origin gets no Access-Control-Allow-Origin with production-shaped empty list; an allowed origin gets it; no Allow-Credentials); an invalid [security] value makes create_app raise before middleware is built.
T12 tests/unit/infrastructure/security/test_security_settings_issuer_validate.py (new): issuer_config as a string or list fails naming the key; an entry with an unknown key, an http jwks_uri on a non-loopback host, algorithms [] or containing HS256 or none each fail naming the issuer and key; http://127.0.0.1:8001 passes; absent algorithms passes (RS256 default kept).
T13 tests/unit/server/test_server_security_bypass_refuse.py (new): create_app under ENVIRONMENT=production with SECURITY__DEV_BYPASS_ENABLED=true, or with SECURITY__DEV_BYPASS_TOKEN set, raises ConfigurationError naming the key before any middleware is built; the same values under local build the app.
T11 tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py (edit): drop the SecuritySettings rows (:86-107, :244-288) and the module docstring lines about ISSUER_CONFIG/CORS (:7-8); tests/unit/bin/test_bin_settings_key_ownership_check.py:555 (table "security" claimed once, env names SECURITY__*); test_security_keys_are_declared_only_by_the_security_slice stays.

== Assumptions and doubts (how to verify) ==
A1 No reader other than those listed uses the old env names (rg above over app/ bin/ terraform/ .github/ .devcontainer/ docs/; include app/.env.example by human).
A2 The blob key is ISSUER_CONFIG in sre-bot-config and the value is JSON (doc-14 line 53): G4 compares a hash so format drift (quotes, whitespace, key order) cannot slip through.
A3 A TOML table with URL keys round-trips to the same dict: T6/T7 and G4.
A4 The ownership script accepts a table in infrastructure/security (111.3 scans all non-test python): run make check-settings-key-ownership.
A5 The CORS env/terraform entry stays set and unread after the deploy: harmless; but it becomes a dead knob (a terraform change to cors_allowed_origins no longer changes CORS). Called out for 111.15.1 and in the PR description; terraform is untouched here to keep one subsystem.

== Blast radius and rollback ==
Merge to main deploys; terraform is untouched, so tf_apply does not run. Failure modes: (1) invalid or missing [security] key: create_app raises, the task never stabilises, the circuit breaker rolls back in ~5 min (workflow red, Slack notified). (2) QUIET, highest risk: issuer_config copied wrongly or empty: boot succeeds in the degraded mode (security_services_no_issuer_config warning, /health static) and every authenticated request fails. Guards: T7, G4 hash match, V5. (3) CORS widening: only if someone adds an origin to production.toml (reviewed file) or a wildcard (rejected at boot by the validator, T5); with production origins empty the preflight must show no Access-Control-Allow-Origin (V6). (4) Dev bypass accidentally enabled in production: needs both SECURITY__DEV_BYPASS_ENABLED=true and a token AND ENVIRONMENT != production; production has no parameter, no env entry and no file key (T7, V3, V9); the environment guard still refuses (T8). Rollback: git revert restores code; faster, Actions page (admin) build_and_deploy.yml with image_tag=<previous tag from G5> per docs/runbooks/roll-back-a-deployment.md; never aws ecs update-service outside the runbook's break-glass. The previous image reads ISSUER_CONFIG from the .env that entry.sh still writes from the blob and CORS_ALLOWED_ORIGINS from the task definition, both still supplied (111.15.1 not merged): rollback is complete. A rolled-back deploy leaves main on the new code: revert or fix forward before the next merge. Ordering constraint: 111.15.1/111.15.2 must not merge until 111.8 has been deployed and stable (they delete the names a 111.8 rollback needs).

== Merge gates (human, before merge) ==
G1 TASK-111.7 merged (#1776), its deploy passed V1-V8 and its DoD is checked; the 111.8 branch was cut from main after that merge.
G2 No renamed-secret parameter is needed, and none for the bypass: aws ssm describe-parameters --region ca-central-1 --parameter-filters "Key=Name,Option=BeginsWith,Values=/sre-bot/" --query 'Parameters[].Name' --output text  -> exactly the 11 names in ssm.tf:19-29, none starting /sre-bot/SECURITY__ (names only, never get-parameter on these).
G3 Baseline recorded in the notes: latest security_services_initialized issuer_count from the 111.7 deploy (expected 1): aws logs filter-log-events --region ca-central-1 --log-group-name /ecs/sre-bot-app --start-time $(date -u -d '24 hours ago' +%s)000 --filter-pattern '"security_services_initialized"' --query 'events[-1].message' --output text
G4 production.toml issuer entry generated from and equal to the blob value (the blob also holds secrets: pipe, never print it whole). (a) keys check, expect only jwks_uri, algorithms, audience: aws ssm get-parameter --region ca-central-1 --name sre-bot-config --with-decryption --query Parameter.Value --output text | sed -n 's/^ISSUER_CONFIG=//p' | tr -d "'" | jq -c 'map_values(keys)' . (b) append the entry: same pipeline | jq -r 'to_entries[] | "\n[[security.issuers]]\nissuer = \(.key|tojson)\njwks_uri = \(.value.jwks_uri|tojson)\n" + (if .value.algorithms then "algorithms = \(.value.algorithms|tojson)\n" else "" end) + "audience = \(.value.audience|tojson)"' >> app/config/production.toml . (c) hash match: blob side same pipeline | jq -S -c 'map_values(.algorithms //= ["RS256"])' | sha256sum ; file side cd app && uv run python -c "import json; from contracts.configuration import install_configuration_files; from server.configuration import load_configuration_files; install_configuration_files(load_configuration_files('production')); from infrastructure.security.settings import SecuritySettings; print(json.dumps(SecuritySettings(_env_file=None).issuer_config, sort_keys=True, separators=(',',':')))" | tail -1 | sha256sum (tail drops startup log lines). Equal hashes.
G5 Previous image tag and digest recorded for rollback: aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service --query 'services[0].deployments[?status==`PRIMARY`].taskDefinition' --output text ; aws ecs describe-task-definition --region ca-central-1 --task-definition <that arn> --query 'taskDefinition.containerDefinitions[0].image' --output text
G6 Gates green from app/: ruff check . ; mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files; baseline 47) ; pytest tests --ignore=tests/smoke ; make check-import-contracts ; make check-settings-key-ownership.
G7 Human: app/.env.example edited as listed under Cleanup; local app/.env uses SECURITY__ names (a developer using the bypass sets SECURITY__DEV_BYPASS_ENABLED and SECURITY__DEV_BYPASS_TOKEN).
G8 Merge outside a deploy in progress (concurrency group ecs-deploy queues anyway); someone able to run the Actions page rollback (admin) is available for the 30 minutes after merge.

== Post-deploy checklist (Linux Codespace, zsh, GNU date; read-only; production changes only via GitHub Actions; gh cannot start or re-run workflows here, HTTP 403: dispatch or re-run from the Actions page as an admin; never print parameter values, never local build/registration/update-service) ==
V1 gh run list --workflow build_and_deploy.yml --limit 3 ; gh run watch <run-id> --exit-status. ~3-4 min plus the alarm bake; the workflow waits up to 15 min. Expect success (a red post-deploy SBOM step from the trivy-db rate limit is a known unrelated failure).
V2 aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service --query 'services[0].deployments[].[status,rolloutState,taskDefinition,runningCount]' --output table. Expect one PRIMARY COMPLETED on a new revision.
V3 Names only: aws ecs describe-task-definition --region ca-central-1 --task-definition sre-bot-task --query 'taskDefinition.containerDefinitions[0].[secrets[].name,environment[].name]' --output json. Expect the same names as 111.7 V3 (CORS_ALLOWED_ORIGINS still present, now unread) and NO name starting SECURITY__ in secrets or environment.
V4 Boot errors: aws logs filter-log-events --region ca-central-1 --log-group-name /ecs/sre-bot-app --start-time $(date -u -d '15 minutes ago' +%s)000 --filter-pattern '?ValidationError ?ConfigurationError ?Traceback ?"configuration files not loaded"' --query 'events[].message' --output text. Expect empty.
V5 Issuers loaded: same command with --filter-pattern '"security_services_initialized"' --query 'events[].message'. Expect issuer_count equal to the G3 baseline on each new task. Then --filter-pattern '?security_services_no_issuer_config ?issuer_config_not_set ?issuer_missing_jwks_uri ?jwks_warmup_skipped_no_issuer_config' returns nothing.
V6 CORS: curl -s -i -X OPTIONS https://sre-bot.cdssandbox.xyz/version -H 'Origin: https://example.com' -H 'Access-Control-Request-Method: GET' | grep -i '^access-control' . Expect no output (no Access-Control-Allow-Origin, no Allow-Credentials). Repeat with a simple GET: curl -s -i https://sre-bot.cdssandbox.xyz/version -H 'Origin: https://example.com' | grep -ci '^access-control' prints 0.
V7 Auth rejects bad tokens: curl -s -o /dev/null -D - https://sre-bot.cdssandbox.xyz/api/v1/access/catalog | grep -iE '^(HTTP|www-authenticate)' expects 401 with WWW-Authenticate: Bearer; the same with -H 'Authorization: Bearer not.a.token' expects 401. If the route returns 404 it is not mounted in production: record N/A and rely on V5 (as 111.5.1 check 6 did).
V8 Auth accepts a valid token (human holding a Backstage or service token carrying scope sre-bot:access-catalog; read it with read -s TOKEN, never paste it into history or notes): curl -s -o /dev/null -w '%{http_code}\n' https://sre-bot.cdssandbox.xyz/api/v1/access/catalog -H "Authorization: Bearer $TOKEN" . Expect anything but 401/403 (503 "feature disabled" is a pass: auth succeeded and the handler ran). If no token is available: N/A, V5 plus unchanged issuer_count is the evidence; say so in the notes.
V9 Dev bypass disabled: (a) V3 shows no SECURITY__ name; (b) aws ssm describe-parameters --region ca-central-1 --parameter-filters "Key=Name,Option=BeginsWith,Values=/sre-bot/SECURITY" --query 'Parameters[].Name' --output text prints nothing; (c) aws logs filter-log-events ... --start-time $(date -u -d '30 minutes ago' +%s)000 --filter-pattern '"dev_bypass_token_used"' --query 'events[].message' prints nothing; (d) curl -s -o /dev/null -w '%{http_code}\n' https://sre-bot.cdssandbox.xyz/api/v1/access/catalog -H 'Authorization: Bearer dev-token' prints 401.
V10 Regression: curl -s https://sre-bot.cdssandbox.xyz/version shows the deployed SHA from the run summary; curl -s -o /dev/null -w '%{http_code}\n' https://sre-bot.cdssandbox.xyz/health prints 200.
Rollback on any failure: Actions page, build_and_deploy.yml with image_tag=<tag from G5> (admin), then verify with the runbook; revert the merge.

== Cleanup (by location, with timing) ==
- app/.env.example (unreadable to agents; HUMAN edit, in the PR before merge, G7): replace ISSUER_CONFIG, DEV_BYPASS_ENABLED, DEV_BYPASS_TOKEN lines with SECURITY__ISSUER_CONFIG, SECURITY__DEV_BYPASS_ENABLED, SECURITY__DEV_BYPASS_TOKEN (commented, "local development only; never set in production"); delete CORS_ALLOWED_ORIGINS/METHODS/HEADERS lines and add a note that the lists live in app/config/base.toml [security]. Confirm: rg -n 'ISSUER_CONFIG|DEV_BYPASS|CORS_ALLOWED' app/.env.example shows only SECURITY__ names.
- Local app/.env, any time after merge: rename the same names to SECURITY__ (the old names are ignored, so a stale bypass setting silently stops working; confirm with the dev bypass test call). Confirm: rg -n 'ISSUER_CONFIG|DEV_BYPASS|CORS_ALLOWED' app/.env.
- Codespaces secrets, after V1-V10 pass: gh secret list --app codespaces ; delete any of ISSUER_CONFIG, DEV_BYPASS_ENABLED, DEV_BYPASS_TOKEN, CORS_ALLOWED_ORIGINS/METHODS/HEADERS that exist (gh secret delete <NAME> --app codespaces). Older branches default to the code values; none expected to exist.
- GitHub Actions secrets/variables: none (rg over .github/ is clean); nothing to delete. Confirm: rg -n 'ISSUER_CONFIG|DEV_BYPASS|CORS' .github/ prints nothing.
- pyproject.toml pytest env ISSUER_CONFIG: deleted in this PR.
- SSM: blob sre-bot-config key ISSUER_CONFIG: NO edit now (rollback image reads it); removed with the blob by 111.15.2 (terraform). The renamed SecureStrings: unchanged, no SECURITY__DEV_BYPASS_TOKEN parameter exists or is created. Confirm: G2 output unchanged after the deploy.
- Task definition (terraform): CORS_ALLOWED_ORIGINS env stays, unread, until TASK-111.15.1 removes ecs.tf:34, sre-bot.json.tpl:57-58 and variables.tf:46 through terraform. Not removed here: terraform in the same PR would be a second subsystem and would break the previous-image rollback. Confirm after 111.15.1: V3 lists no CORS_ALLOWED_ORIGINS.

== Decisions assessed 2026-10-23 (ADRs and doc-11 scope; recommendation first) ==
Q1 Fail boot on a bad issuer entry. ADR: covered for the principle, gap for the detail. configuration.md "Fail fast" (an invalid file fails boot naming the key) and lifecycle.md "Only deploy-coupled defects abort boot" (checked-in configuration) cover it; the lenient non-object -> {} branch violates them. security.md fails boot only on a missing audience; a wrong algorithm list or jwks_uri degrades silently. lifecycle.md's "JWKS issuer gaps" degraded start is about runtime reachability (state that changes without a deploy), not file shape. Upcoming tasks: TASK-116 moves the code with "no behaviour change"; TASK-156 only logs. Practice: RFC 8725 3.1 (callers specify the algorithm set; no other used) and 3.9; OpenID Connect Discovery 1.0 (jwks_uri uses https); ASP.NET Core ValidateOnStart and Spring Boot @Validated configuration properties fail startup on invalid options. RECOMMEND: step 7 in this PR; security.md Authentication clause amended: "Each issuer entry is boot-validated: only jwks_uri, algorithms and audience; jwks_uri https (http only on a loopback host); algorithms a non-empty subset of the asymmetric set, RS256 when absent; audience required. Fail-degraded applies to JWKS reachability only." TASK-116 gains an AC for a typed frozen issuer entry.
Q2 Boot refusal for the dev bypass in production. ADR: gap. security.md requires the two per-request guards and logging of use; it is silent on the flag or token being present in production. lifecycle.md classes a checked-in configuration defect as boot-fatal, and TASK-156 AC #4 would only WARN. Practice: OWASP ASVS 5.0 V13.4.2 (debug modes disabled in production, L2); Spring Boot DevTools disabled in packaged applications and "never enable on a production deployment"; Django check --deploy security.W018 (DEBUG on in a deployment) is only a warning and runs only on request, the weakness a boot refusal avoids. RECOMMEND (reversing the 2026-10-22 NO): step 6 in this PR, about 10 lines; security.md Dev bypass clause adds "In production, the flag on or a token present fails boot naming the key." TASK-156 AC #4 narrows to the WARNING outside production and for an empty issuer list. Safe now: production has no SECURITY__ name (G2, V3) and the files set none (T7).
Q3 Bypass flag in local.toml. ADR: covered. configuration.md "Environment identity": security toggles need "their own explicit boolean that defaults off: two independent guards"; a local.toml true makes the flag follow ENVIRONMENT, so the guards stop being independent. No task changes it. RECOMMEND: NO, opt-in per developer through SECURITY__DEV_BYPASS_ENABLED and the token in app/.env.
Q4 Added AC #4, #5 and DoD #1-2. ADR: covered. configuration.md Checks (unknown key fails boot naming file, table and key) and security.md Checks (missing aud fails boot, CORS wildcard rejected) require these tests. RECOMMEND: keep; AC #6 (Q1) and AC #7 (Q2) added, strike them if Q1/Q2 are declined.
Q5 Dead terraform cors_allowed_origins. ADR: covered. configuration.md "Renaming an environment name" removes the old name once the deploy is verified (parallel change), and TASK-111.15.1 drops CORS_ALLOWED_ORIGINS from the task definition. RECOMMEND: leave it; 111.15.1 now names variables.tf and the template line; one-line warning in the PR description.
Also: configuration.md:17 still names the unprefixed variables; this PR updates it (S4a).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-23. Plan approved (Q1 and Q2 yes, Q3 no, Q4 keep, Q5 leave). Amended with the human before coding: issuers are an array of tables, [[security.issuers]] (any number of entries), because the loader's lower snake_case rule rejects an issuer URL as a table name (verified on a copy of the files).

Changes:
- infrastructure/security/settings.py: SecuritySettings is a ConfigurationSlice on [security], prefix SECURITY__, extra=forbid, no alias. issuers: list[IssuerEntry] (frozen, extra=forbid) with boot validation: https jwks_uri (http only on 127.0.0.1, ::1, localhost), non-empty asymmetric algorithms (RS256 when absent), audience required, one entry per issuer. Each error names the issuer and key. issuer_config is now a read-only property keyed by issuer, so jwks.py, jwt.py and the lifespan readers are unchanged. ASYMMETRIC_ALGORITHMS moved here; jwt.py imports it. The CORS wildcard checks are field validators, so the error names the list. The lenient non-object -> {} branch is gone.
- contracts/configuration.py: a file error names the full location (issuers.0.audience), not only the top-level key.
- server/configuration/host_configuration.py: refuse_dev_bypass_in_production runs in the configuration phase of create_app and raises ConfigurationError when production has dev_bypass_enabled or SECURITY__DEV_BYPASS_TOKEN.
- app/config/base.toml: [security] (no issuers, empty origins, GET/POST, the default headers, bypass off). production.toml: the issuer entry is still to be added by the human (G4).
- pyproject.toml: pytest ISSUER_CONFIG removed. bin/dev-token.py prints SECURITY__ISSUERS. Log detail text in jwks.py and lifespan.py names [security] issuers; event names unchanged (V5 filters still match). current_user.py docstrings use the new names.
- decisions/security.md: Authentication and Dev bypass clauses amended, with a 2026-10-23 entry. decisions/configuration.md: line 17 and a 2026-10-23 entry.

Tests:
- New: test_security_settings_issuer_validate.py, test_security_settings_production_values.py, test_server_dev_bypass_refuse.py.
- Rewritten: test_security_settings_load.py (includes the retired unprefixed names being ignored).
- Updated: test_security_jwks_issuer_config.py, test_current_user_bypass.py, test_server.py, test_lifespan_security_settings_validation.py. The security rows are dropped from test_configuration_settings_production_names.py.

Gates:
- ruff check . : All checks passed. ruff format: clean.
- mypy: 47 errors in 18 files (baseline), none in touched files.
- pytest tests --ignore=tests/smoke: 5675 passed, 1 failed. The failure is test_production_trusts_exactly_one_issuer, red until the human appends the production issuer entry (G4).
- make check-import-contracts: 12 kept, 0 broken. make check-settings-key-ownership: OK.
- G4 generator and hash commands dry-run on a sample value: entry generated, hashes equal once startup log lines are dropped (tail -1).

Open:
- Human: G4 (append the production entry, hash match), the app/.env.example edit (the agent's read of it is denied), then G1-G3 and G5-G8 at merge. AC #1, #3 and #5 close after G4.
- Follow-up candidate, not created: ConfigurationSlice attributes an error to the file holding the key even when an env var or keyword argument supplied the bad value (pre-existing, all slices).
- TASK-116 AC #5 rescoped: readers take the IssuerEntry list and the issuer_config property is deleted.

2026-10-23, G4 done by the human: production.toml carries the one production issuer (https://backstage.cdssandbox.xyz/api/auth, ES256, audience backstage), generated from the sre-bot-config blob. The blob line is 'ISSUER_CONFIG = '...'' with spaces around '=', so the G4 sed in the plan needs the space-tolerant pattern. Re-run: ruff clean, 5676 passed, key ownership OK, contracts 12 kept. All ACs checked. Open for the human: the hash-match result, the app/.env.example edit, G1-G3 and G5-G8 at merge, then V1-V10.

2026-10-23, G2 G4-G8 passed (human), G3 baseline issuer_count = 1 (every boot logged in the window, no missing-issuer warning; the newest boot after the 111.7 deploy is checked as part of G1). filter-log-events over a multi-day window hangs on this log group: use Logs Insights for G3, V4, V5 and V9, e.g. aws logs start-query --region ca-central-1 --log-group-name /ecs/sre-bot-app --start-time $(date -u -d '30 minutes ago' +%s) --end-time $(date -u +%s) --query-string 'filter @message like /security_services|dev_bypass_token_used|ConfigurationError|ValidationError|Traceback/ | sort @timestamp desc | limit 50' --query queryId --output text, then aws logs get-query-results --region ca-central-1 --query-id <id>.

Correction to the Insights tip: read the results with --output json | jq -r '.status, (.results[][] | select(.field == "@message") | .value | (fromjson? // {event: "non-json line"}) | "\(.timestamp // "-")  \(.event)  \(.issuer_count // "")")' (the JMESPath filter form fails to parse).

2026-10-23, pre-merge gates (human, script check-now.zsh): G2 pass (11 parameters at Version 2, no /sre-bot/SECURITY__). G3 baseline issuer_count 1 (both 111.7 tasks at 13:29 UTC). G4 MATCH. G5 rollback target: sre-bot-task:41, image sre-bot@sha256:28f828355208526a8e8621040cd809ed8a969b69efcf588590bcc4e9c5a662b3 (tag still to read from ECR). G6 pass: ruff clean, mypy 47 (baseline), 5676 passed, contracts 12 kept, key ownership OK. G7 pass: .env.example carries only SECURITY__ names. G1 open: 111.7 V4/V8 (two non-JSON lines in the boot window) and the 111.7 DoD #1 image record.

2026-10-23: G1 pass (111.7 V1-V8 passed, its ACs and DoD checked). G5 rollback tag: image_tag=52282a9c0dc8222825b8335caaecaef8eafd2e72-2026-10-23 (sre-bot-task:41, sha256:28f82835...). G8 is checked at merge, then DoD #1.
<!-- SECTION:NOTES:END -->
