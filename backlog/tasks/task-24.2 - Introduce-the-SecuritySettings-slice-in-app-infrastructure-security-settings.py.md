---
id: TASK-24.2
title: >-
  Introduce the SecuritySettings slice in
  app/infrastructure/security/settings.py
status: Done
assignee:
  - '@me'
created_date: '2026-10-19 17:18'
updated_date: '2026-10-20 13:02'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
  - decisions/plugins.md
parent_task_id: TASK-24
priority: medium
ordinal: 400000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-24 (decisions/configuration.md: the security domain owns a SecuritySettings slice). Security config is split today: DEV_BYPASS_ENABLED and CORS_ALLOWED_ORIGINS/METHODS/HEADERS with the wildcard validator on AppSettings (app/infrastructure/configuration/app.py), ISSUER_CONFIG and DEV_BYPASS_TOKEN with their validators on ServerSettings (app/infrastructure/configuration/infrastructure/server.py). The slice is built where security lives today; TASK-116 carries it to app/server/security/.

Consumers: server/server.py CORSMiddleware, infrastructure/security/current_user.py (dev bypass), infrastructure/security/jwks.py and server/lifespan.py (issuers). The slice validates in the lifespan configuration phase with the other host slices.

No rate-limit backend field: the limiter is in-process with one backend (human, 2026-10-19); the field arrives with a second backend. Env names unchanged (renames in TASK-111). Independent of Stack K.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 SecuritySettings in app/infrastructure/security/settings.py is the only class that defines ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS (with the wildcard-with-credentials validator), DEV_BYPASS_ENABLED and DEV_BYPASS_TOKEN; AppSettings and ServerSettings no longer declare them, and the slice declares no per-field alias
- [x] #2 The CORS middleware (server/server.py), the dev bypass (infrastructure/security/current_user.py), JWKS (infrastructure/security/jwks.py) and lifespan read get_security_settings(); lifespan's configuration phase validates the slice, and a wildcard CORS value or an issuer without an audience fails boot naming the key
- [x] #3 Env var names are unchanged, and defaults are unchanged except CORS_ALLOWED_METHODS, which defaults to GET and POST, and the CORS middleware, which no longer allows credentials; the wildcard, audience-required and unparseable-ISSUER_CONFIG behaviours are preserved; the moved tests live in a new unit test beside the slice and the legacy tests that set these keys are updated in place
- [x] #4 decisions/configuration.md current-state and migration lines record the single SecuritySettings slice and TASK-116 as its move to app/server/security/; decisions/security.md's CORS rule records no credentials mode and the GET/POST methods default
- [x] #5 ruff, lint-imports, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #6 DEV_BYPASS_TOKEN is a SecretStr whose value appears in neither the slice's repr nor model_dump_json, and the dev bypass compares the bearer token in constant time
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Slice 2 of TASK-24. Move the six security keys into one SecuritySettings slice at app/infrastructure/security/settings.py and repoint their four consumers. A move: env names and validation behaviour do not change, and defaults do not change except two CORS tightenings (below) (renames ride with TASK-111; the file moves to app/server/security/ with TASK-116). Same shape as TASK-24.1. Independent of Stack K and of 24.3-24.5.

Branch from an up-to-date main. Commit 1: the TASK-24.2 planning edits (plan and AC rewrite). Commit 2: the move.

Design decisions
- SecuritySettings subclasses pydantic_settings.BaseSettings directly with model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore"), the convention 24.1 set for moved slices. No import from infrastructure.configuration, so TASK-116 moves the file by path only. Getter get_security_settings() with lru_cache(maxsize=1).
- Fields, defaults and validators move verbatim: ISSUER_CONFIG (dict[str, dict[str, Any]] | None = None, before-validator turning a non-dict, including an unparseable env string, into {}; after-validator rejecting an issuer entry without an audience), CORS_ALLOWED_ORIGINS (default []), CORS_ALLOWED_METHODS (default narrowed to ["GET", "POST"]) and CORS_ALLOWED_HEADERS (same default list), the wildcard-rejection after-validator, DEV_BYPASS_ENABLED (False), DEV_BYPASS_TOKEN (now SecretStr | None, default None: decisions/configuration.md already bans secrets from repr, so the plain str is a bug fixed in a touched file). The per-field alias equal to the field name is dropped (same env name under case_sensitive; the ADR rule bans per-field aliases). No rate-limit field (human decision, 2026-10-19). No env_prefix: names unchanged until TASK-111.
- case_sensitive=True (human, 2026-10-20): in the end state (decisions/configuration.md) the CORS lists, ISSUER_CONFIG and DEV_BYPASS_ENABLED move to TOML with TASK-111 and only the token stays in env as <SLICE>__<FIELD>, so exact-case matching is what the end state expects and matches base.py and every 24.1 vendor slice. Production sources (human, 2026-10-20): ISSUER_CONFIG is the only key in SSM sre-bot-config and was already case-sensitive on ServerSettings; CORS_ALLOWED_ORIGINS comes from the ECS task definition (terraform/templates/sre-bot.json.tpl:62, upper case); CORS_ALLOWED_METHODS/HEADERS are unset (defaults); the dev bypass keys are local .env only. No SSM or terraform change.
- The slice lives beside the code that reads it (human, 2026-10-20): auth is host code bound for app/server/security/ (plugin-architecture.md, authorization.md), but import-linter's layers contract puts server above infrastructure, so current_user.py and jwks.py cannot import a server/ slice. TASK-116 moves the code and the slice together.
- Startup log (human, 2026-10-20): _list_configs_from_sections only gains the slice's key names, so moving the keys off ServerSettings does not drop ISSUER_CONFIG and DEV_BYPASS_TOKEN from today's log. The startup configuration summary redesign (generated slice list, secret presence, identity event, config hash) is TASK-156, after TASK-111.
- CORS tightening (human, 2026-10-20). CORS stays so a self-hosted frontend can be added by configuration. CORS_ALLOWED_METHODS defaults to GET and POST, the only methods the API's routes use (OPTIONS never needs listing; preflight is answered regardless). server/server.py sets allow_credentials=False: the API authenticates with bearer tokens a script puts in the Authorization header, which needs no credentials mode, and nothing in app/ uses cookies or sessions, so a mis-added origin cannot ride a user's cookies. The wildcard validator stays (OWASP: no * for non-public resources, credentials or not). No production effect: the production origin list is empty, so no CORS header is sent. decisions/security.md:22 is amended to say so.
- AppSettings keeps ENVIRONMENT, LOG_LEVEL, GIT_SHA and WEBHOOK_MAX_BODY_BYTES. ENVIRONMENT stays on AppSettings (deployment identity), so the dev-bypass double guard reads ENVIRONMENT from AppSettings and the bypass keys from SecuritySettings.
- The slice validates in lifespan's configuration phase beside the other host slices, via get_security_settings() at the top of lifespan. server/server.py also reads it at import (as it reads AppSettings today), so an invalid value fails at import or boot, naming the key via the validator message.
- No SecuritySettings export from infrastructure/security/__init__.py (human, 2026-10-20: TASK-116 deletes the package with no re-export, so a package export would only be unwound). Consumers import infrastructure.security.settings.

Steps (tests first)
1. New unit test app/tests/unit/infrastructure/security/test_security_settings_load.py (fails: module missing). Fixtures: monkeypatch.setitem(SecuritySettings.model_config, "env_file", None), delenv of the six keys, get_security_settings.cache_clear() before and after. Cases: singleton identity; each field from its unchanged env name (ISSUER_CONFIG and the three CORS lists as JSON, DEV_BYPASS_ENABLED "true", DEV_BYPASS_TOKEN); defaults when unset (issuer None, origins [], default methods/headers, bypass False, token None); wildcard in any of the three CORS lists raises ValidationError naming the key (parametrized, moved from test_app_settings); issuer entry without audience raises naming the issuer (moved from test_infra_settings_singletons); unparseable ISSUER_CONFIG env string (the pyproject pytest env sets ISSUER_CONFIG='test-issuer-config') yields {}; DEV_BYPASS_TOKEN is a SecretStr whose value is absent from repr(slice) and model_dump_json(); model_config shape; AppSettings and ServerSettings no longer declare the six names (model_fields assertion, AC1).
2. New unit test app/tests/unit/infrastructure/security/test_security_jwks_issuer_config.py: get_issuer_config returns the slice's issuers; returns {} and logs issuer_config_not_set when unset; get_jwks_manager builds from the slice (cache_clear around it).
3. New integration test app/tests/integration/server/test_lifespan_security_settings_validation.py, same pattern as test_lifespan_vendor_slice_validation.py (env_file disabled, caches cleared, later phases stubbed): a wildcard CORS origin and an issuer without audience each fail boot with a ValidationError naming the key, before core services are built; valid values boot to yield.
4. Create app/infrastructure/security/settings.py (about 70 LOC: SecuritySettings and get_security_settings, moved code, module docstring in the style of integrations/maxmind/settings.py).
5. Delete the six fields and both validators from app/infrastructure/configuration/app.py (:16, :19-27, :30-46; drop the now-unused model_validator import; fix the AppSettings docstring that says the CORS policy sits here pending SecuritySettings) and from app/infrastructure/configuration/infrastructure/server.py (:47-54 fields, :56-72 validators, the ISSUER_CONFIG and DEV_BYPASS_TOKEN lines in the class docstring :21-24; drop the unused Any, field_validator, model_validator imports).
6. Repoint consumers:
   - server/server.py:7,12,24-27: security_settings = get_security_settings() for the three CORS arguments; app_settings stays for WEBHOOK_MAX_BODY_BYTES (:31).
   - infrastructure/security/current_user.py:43-47,99-105: drop get_server_settings; read DEV_BYPASS_ENABLED and DEV_BYPASS_TOKEN from get_security_settings(), ENVIRONMENT from get_app_settings(); compare the bearer token with secrets.compare_digest against DEV_BYPASS_TOKEN.get_secret_value() (the == comparison is not constant-time, a bug fixed in a touched file); fix docstrings :27-30,:68-70 (they name ServerSettings); add environment to the dev_bypass_token_used warning context (never the token).
   - infrastructure/security/jwks.py:13-15,22-29,49: get_security_settings().ISSUER_CONFIG; the issuer_config_not_set warning names the key and operation (key="ISSUER_CONFIG", operation="get_issuer_config") and no longer says "server settings"; fix the stale settings.server.ISSUER_CONFIG docstring (:49) and the "unified security settings" docstring (:21).
   - server/lifespan.py:20-23,78-100,143-168,243-262: get_security_settings() joins the configuration-phase calls (:243-250 block); _initialize_security_services(security_settings, logger) takes SecuritySettings (reads ISSUER_CONFIG from it) and drops its unused app parameter (human, 2026-10-20: the signature and its one call site change anyway; the six lifespan tests patch it by string target, so none changes); _list_configs_from_sections gains a security_settings parameter and logs its keys (key names only, no values) as config_setting="security".
7. Edit legacy tests in place: test_app_settings.py (delete DEV_BYPASS_ENABLED tests :70-79 and TestAppSettingsCors :105-150, now covered by step 1; fix class docstring :44); test_infra_settings_singletons.py (delete TestServerSettingsIssuerConfigValidation :85-110); test_current_user_bypass.py (:24-100: patch infrastructure.security.current_user.get_security_settings returning a real SecuritySettings(DEV_BYPASS_ENABLED=..., DEV_BYPASS_TOKEN=...) instead of MagicMock; AppSettings(ENVIRONMENT=...) only. Required: AppSettings(DEV_BYPASS_ENABLED=True) would be silently ignored under extra="ignore" and make the tests pass for the wrong reason); test_server.py (:41-43 read server.security_settings; :53-60 patch infrastructure.security.settings.get_security_settings with a SecuritySettings(...) and keep the app settings patch for ENVIRONMENT); tests/integration/server/test_lifespan.py:67-90 (pass the new security_settings argument). pyproject.toml:143 (pytest env ISSUER_CONFIG) is unchanged.
8. Docs: decisions/security.md:22 CORS rule (explicit allow-list from settings, * rejected at boot in every environment, no credentials mode because the API uses bearer tokens, methods default to the ones the API serves) and a dated changelog line; decisions/configuration.md:17 current-state line (security settings now one SecuritySettings slice in infrastructure/security/settings.py, TASK-116 moves it to server/security/) and the migration bullet "security settings split across AppSettings and ServerSettings" is removed.
9. Gates from app/: ruff check ., ruff format --check ., lint-imports, mypy (0 new errors in touched files), pytest tests --ignore=tests/smoke; rg -n "(DEV_BYPASS_ENABLED|DEV_BYPASS_TOKEN|ISSUER_CONFIG|CORS_ALLOWED_)" app --glob '!tests' shows only settings.py, docstrings, terraform names and bin/dev-token.py help text.

Call sites found (path:line)
- Definitions: infrastructure/configuration/app.py:16,19,20,24,34-44; infrastructure/configuration/infrastructure/server.py:21-22,47-53,56,59,67-70.
- Readers: server/server.py:24,26,27; infrastructure/security/current_user.py:99,103-105; infrastructure/security/jwks.py:22-24 (get_issuer_config); server/lifespan.py:157 (settings.ISSUER_CONFIG) and :146 signature; get_jwks_manager (jwks.py:133) goes through get_issuer_config.
- Tests that set or read them: tests/unit/infrastructure/configuration/test_app_settings.py:44,70-79,114-150; test_infra_settings_singletons.py:85-109; tests/unit/infrastructure/security/test_current_user_bypass.py:24-100; tests/unit/server/test_server.py:41-43,53-60; tests/integration/server/test_lifespan.py:67-90 (settings mocks, signature only); tests/integration/server/test_lifespan_{core_services,plugin_loading,scope_opener,slack_start_log,legacy_slack_commands_registration,vendor_slice_validation}.py patch _initialize_security_services whole (no edit). No conftest sets or overrides any of the keys.
- Config and docs: pyproject.toml:143 (pytest env ISSUER_CONFIG, unchanged); terraform/templates/sre-bot.json.tpl:62 and terraform/ecs.tf:28, variables.tf:46 (CORS_ALLOWED_ORIGINS, name unchanged, no edit); app/bin/dev-token.py:6,14,15,183,185 (help text naming ISSUER_CONFIG, still correct, no edit); decisions/security.md:20, lifecycle.md:15 (names only, no edit); decisions/configuration.md:17,77.
- Not found: no settings.server.* or settings.app.* attribute access (the Settings aggregator is gone); no .github/workflows reference; no app/bin script other than dev-token.py; no import-linter ignore entry for these modules. app/.env.example is outside my read permission: the implementer must check it for the four names.

AC traceability
- AC1 (one class, fields gone from AppSettings/ServerSettings) <- steps 4, 5; tests step 1 (model_fields assertions, defaults, validators).
- AC2 (consumers read the slice; boot validation) <- steps 6; tests step 1-3, 7.
- AC3 (names and validation behaviour unchanged; defaults unchanged but the two CORS tightenings) <- steps 4, 6; tests step 1 and tests/unit/server/test_server.py (no Access-Control-Allow-Credentials on a preflight from an allowed origin; methods default); tests step 1 (env names, defaults, unparseable ISSUER_CONFIG, wildcard, audience).
- AC4 (docs: configuration.md and security.md) <- step 8.
- AC5 (gates) <- step 9.

Test matrix: happy (each field from its env name; valid boot); boundary (unset defaults; unparseable ISSUER_CONFIG gives {}; empty issuer map); failure (wildcard in each CORS list; issuer without audience; invalid slice fails boot before core services); authorization (dev bypass denied in production, denied when the flag is false, denied on a wrong token, allowed when ENVIRONMENT is not production and flag and token match; token never logged nor shown in repr); idempotency: singleton identity.

Size gate: production files 8 (settings.py new about 70 LOC; app.py about -30; server.py about -28; current_user.py about 15; jwks.py about 12; lifespan.py about 15; server/server.py about 6) plus 1 ADR file; about 180 changed production LOC, one subsystem (app code, no terraform or CI), no mechanical-plus-behaviour mix, revertible by one git revert. Tests: 3 new files, 5 edited. Passes the gate; total file count including tests is about 17, as with 24.1.

Assumptions and doubts
- case_sensitive=True is new for these keys (AppSettings matched names case-insensitively). Terraform and the pytest env use upper-case names; the defaults fail closed (empty origins, bypass off). Verified 2026-10-20: no lower-case spelling in terraform/ or SSM (ISSUER_CONFIG is the only SSM key and was already case-sensitive); only a lower-case local .env entry for a dev bypass key would stop matching, and it fails closed.
- app/.env.example could not be read during planning. Verify: the implementer checks it for the six names and updates it only if a name or default it shows changes (none should).
- An unparseable ISSUER_CONFIG string becoming {} comes from pydantic-settings returning the raw string for a union-with-None complex field, then the before-validator. Verify with the step 1 characterization test after the move (the survey ran it on ServerSettings and got {}).
- WEBHOOK_MAX_BODY_BYTES keeps its redundant alias on AppSettings: not a moved field; left for the slice that owns it.
- TASK-24.6's duplicate-key check should find each of the six names on exactly one class after this slice; step 1 asserts it for AppSettings and ServerSettings.

Blast radius and rollback: an import or validation error here stops the app at import or boot, and wrongly cased env names would silently fall back to safe defaults (CORS closed, bypass off, issuers empty so authenticated routes return 500 as today). Covered by the step 3 boot tests and the full pytest run. One git revert restores everything; no env, terraform or deploy change; no ordering constraint with other tasks. TASK-116 later moves settings.py unchanged to app/server/security/.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- New app/infrastructure/security/settings.py: SecuritySettings (env_file .env, case_sensitive, extra ignore; no per-field aliases) and get_security_settings(). It owns ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS, DEV_BYPASS_ENABLED and DEV_BYPASS_TOKEN, with the issuer-audience and CORS-wildcard validators moved unchanged in effect.
- Removed those fields and validators from AppSettings (infrastructure/configuration/app.py) and ServerSettings (infrastructure/configuration/infrastructure/server.py).
- Consumers read the slice: server/server.py (CORS), infrastructure/security/current_user.py (dev bypass), infrastructure/security/jwks.py (issuers), server/lifespan.py (configuration phase builds the slice; _initialize_security_services(settings, logger) takes it and drops the unused app parameter; the startup log lists the slice's key names under config_setting="security").
- Human-approved tightenings (2026-10-20): CORS_ALLOWED_METHODS defaults to GET and POST; the CORS middleware sets allow_credentials=False. No production effect while the origin list is empty.
- Fixes in touched files: DEV_BYPASS_TOKEN is SecretStr (out of repr and JSON); the bypass compares tokens with secrets.compare_digest; dev_bypass_token_used logs the environment; issuer_config_not_set now fires when no issuers are configured (it checked "is not None", but pydantic-settings validates the default, so unset ISSUER_CONFIG is {} and the warning never fired) and names key and operation; stale docstrings in jwks.py, current_user.py, app.py and server.py corrected.
- ADRs: decisions/configuration.md current state and changelog (split-security tolerance closed); decisions/security.md CORS rule (no credentials mode, GET/POST default) and changelog.
- Env var names unchanged. Unset ISSUER_CONFIG stays {} as before (verified against main's ServerSettings).

Tests
- New: tests/unit/infrastructure/security/test_security_settings_load.py, tests/unit/infrastructure/security/test_security_jwks_issuer_config.py, tests/integration/server/test_lifespan_security_settings_validation.py.
- Updated in place: test_app_settings.py and test_infra_settings_singletons.py (moved tests removed), test_current_user_bypass.py (real SecuritySettings instead of MagicMock; AppSettings(DEV_BYPASS_ENABLED=True) would have been silently ignored; adds the unset-token case), tests/unit/server/test_server.py (adds a preflight test: no Access-Control-Allow-Credentials, no PUT), test_server_integration.py, test_lifespan.py.

Gates (from app/)
- uv run ruff check . : All checks passed
- uv run ruff format --check . : 984 files already formatted
- uv run lint-imports : 12 kept, 0 broken
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' : 48 errors in 19 files, none in a touched file (pre-existing)
- uv run pytest tests --ignore=tests/smoke : 5389 passed

Left for the human
- app/.env.example was unreadable in this session (permission denied): check whether it lists the six names; names are unchanged, so only the CORS_ALLOWED_METHODS default comment, if any, could be stale.
- No SSM or terraform change needed: ISSUER_CONFIG is the only security key in SSM and was already case-sensitive; CORS_ALLOWED_ORIGINS comes from the ECS task definition.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-20 12:32
---
2026-10-20 human decisions: case_sensitive=True; slice key names only in the startup log, the redesign is TASK-156; consumers import infrastructure.security.settings directly; drop the unused app parameter of _initialize_security_services. Human step before merge: confirm SSM sre-bot-config uses upper-case names for the six keys.
---

created: 2026-10-20 12:39
---
2026-10-20 correction: no SSM check needed. ISSUER_CONFIG is the only security key in SSM and was already case-sensitive on ServerSettings; CORS_ALLOWED_ORIGINS comes from the ECS task definition; CORS methods/headers use defaults; dev bypass keys are local .env only. Plan approved 2026-10-20.
---

created: 2026-10-20 12:50
---
2026-10-20 human: CORS kept (a self-hosted frontend is possible); methods default narrowed to GET/POST and allow_credentials set to False, both in this PR. Plan approved 2026-10-20.
---
<!-- COMMENTS:END -->
