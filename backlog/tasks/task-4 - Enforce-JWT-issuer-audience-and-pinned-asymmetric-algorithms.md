---
id: TASK-4
title: 'Enforce JWT issuer, audience, and pinned asymmetric algorithms'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 17:19'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1258'
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Authentication). Today app/infrastructure/security/jwt.py:116-122 passes audience=cfg.get("audience") (None when unconfigured, so PyJWT skips the aud check), never passes issuer= to decode, and takes algorithms from config (algorithms=cfg.get("algorithms", ["RS256"])) with no asymmetric-only pinning, leaving an HS256-confusion path (SEC-3, OWASP API2:2023).

Steps in app/infrastructure/security/jwt.py:
1. Require an audience in every issuer config; a config entry without an audience fails boot (validation at settings load).
2. Pass issuer= to jwt.decode and match it to the issuer whose JWKS verified the token.
3. Pin algorithms to the asymmetric set configured per issuer (e.g. RS256/ES256); reject any HS* algorithm regardless of config; never read the algorithm from the token.
4. Validate exp always; validate nbf when present.
5. Keep JWKS fail-degraded semantics: a missing/unreachable issuer 401s its tokens; the app still serves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Boot fails when an issuer config lacks an audience (test exists)
- [ ] #2 decode() receives issuer= and audience=; a token with wrong iss or aud is rejected (tests exist)
- [ ] #3 An HS256-signed token is rejected even if HS256 appears in configuration (test exists)
- [ ] #4 A token with valid signature but expired exp, or future nbf, is rejected
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass, including the four cases above
- [ ] #2 PR references SEC-3 and decisions/security.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope reassessment (2026-07-24): task-2 (CORS) and task-3 (rate-limiter bypass) are Done; task-24 (SecuritySettings slice) is still To Do, so ISSUER_CONFIG stays on the live app/infrastructure/configuration/infrastructure/server.py:ServerSettings (the parallel infrastructure/security/settings.py:SecuritySettings.jwks is unused dead code -- not wired into jwks.py's get_issuer_config(), do not touch it here; note for task-24). Original task file/line anchor (jwt.py:116-122) still matches current code. No decision-record changes needed; decisions/security.md Authentication clause is unchanged and is the binding spec.

Step 1 -- Boot-time audience requirement (AC #1)
File: app/infrastructure/configuration/infrastructure/server.py
- Add `from pydantic import model_validator` (alongside existing Field, field_validator import at line 6).
- Add a `@model_validator(mode='after')` method on ServerSettings, after the existing `validate_issuer_config` field_validator (line ~57), e.g. `validate_issuer_config_requires_audience`: iterate `self.ISSUER_CONFIG.items()` (always a dict post field_validator) and `raise ValueError(f\"ISSUER_CONFIG entry for issuer '{issuer}' is missing required 'audience' (SEC-3, see decisions/security.md)\")` when `not cfg.get('audience')`. Return `self`.
- This mirrors the existing CORS wildcard+credentials pattern in app/infrastructure/configuration/app.py:30-43 (model_validator raising ValueError -> pydantic ValidationError at construction = boot failure).
- Confirmed safe default: pytest's global env sets `ISSUER_CONFIG='test-issuer-config'` (invalid JSON) which the existing before-validator already reduces to `{}` (verified via `uv run python`), so the new after-validator has nothing to iterate in the default test environment -- no test-suite-wide breakage.

Step 2 -- decode() hardening (AC #2, #3, #4)
File: app/infrastructure/security/jwt.py, function validate_jwt_token (currently lines 67-122)
- Add a module-level constant near the top (after the logger, ~line 15): `ASYMMETRIC_ALGORITHMS = frozenset({'RS256','RS384','RS512','ES256','ES384','ES512','PS256','PS384','PS512'})`.
- After `cfg = jwks_manager.issuer_config.get(issuer)` (line 105) and before calling `jwks_client.get_signing_key_from_jwt` (line 111), add fail-fast checks (no network call wasted on a misconfigured/attacked issuer):
  - `audience = cfg.get('audience')`; if falsy, log `issuer_missing_audience` and `raise HTTPException(401, 'Invalid token')`.
  - `configured_algorithms = cfg.get('algorithms', ['RS256'])`; `algorithms = [a for a in configured_algorithms if a in ASYMMETRIC_ALGORITHMS]`; if empty, log `issuer_no_permitted_algorithms` (include configured_algorithms for diagnosis) and `raise HTTPException(401, 'Invalid token')`. This guarantees HS* (or any non-pinned value) is never passed to `decode`, regardless of what is in config -- satisfies AC #3 even for a JWKSManager built directly (bypassing the new settings-load check, e.g. a future non-Settings config source).
- Change the `decode(...)` call (lines 112-117) to: `algorithms=algorithms` (the filtered list, not raw cfg), `audience=audience`, add `issuer=issuer` (new kwarg), and change `options=` to `{'require': ['exp'], 'verify_exp': True, 'verify_nbf': True}` (require forces rejection of tokens with no exp claim at all; verify_nbf is PyJWT's default True already but made explicit here since decisions/security.md calls it out as a distinct, non-negotiable check).
- No change to get_issuer_from_token/extract_user_info_from_token (out of scope) or to the untrusted-issuer/missing-jwks_uri branches above line 105.

Step 3 -- Tests
File: app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py (extends existing TestServerSettingsSingleton area)
- New test class TestServerSettingsIssuerConfigValidation:
  - test_issuer_config_missing_audience_raises_validation_error: `ServerSettings(ISSUER_CONFIG={'iss1': {'jwks_uri': 'https://x/jwks.json', 'algorithms': ['RS256']}})` raises pydantic ValidationError. (AC #1)
  - test_issuer_config_with_audience_is_valid: same shape plus `'audience': 'aud1'` constructs without raising and round-trips the value. (regression guard)

File: app/tests/unit/infrastructure/security/test_jwt.py (extends TestValidateJWTToken)
- Add a session-scoped fixture (local to this file or added to conftest.py) generating one EC P-256 keypair via `cryptography.hazmat.primitives.asymmetric.ec` (mirrors app/bin/dev-token.py's approach) so tests exercise the real, unmocked `jwt.decode` call for genuine PyJWT enforcement (not a mocked decode -- the ACs specify \"valid signature but expired/future\" cases, which requires a real signature).
- Helper to mint a token (`jwt.encode(payload, private_key, algorithm='ES256')`) and a helper issuer_config fixture using `algorithms: ['ES256']`.
- Pattern for each new test: patch `infrastructure.security.jwt.get_issuer_from_token` to return the configured issuer, patch `manager.get_jwks_client` (or the JWKSManager's cached client) so `get_signing_key_from_jwt` returns a MagicMock whose `.key` is the real EC public key -- leave `infrastructure.security.jwt.decode` UNPATCHED so real PyJWT verification runs.
- New tests:
  - test_validate_jwt_token_passes_issuer_and_audience_to_decode: mock `decode` (kwargs-capturing) for a lightweight wiring check that `issuer=`, `audience=`, filtered `algorithms=`, and `options={'require': ['exp'], 'verify_exp': True, 'verify_nbf': True}` are all passed. (AC #2 wiring)
  - test_validate_jwt_token_rejects_wrong_audience: real token minted with `aud` != configured audience -> real decode raises InvalidAudienceError -> 401. (AC #2)
  - test_validate_jwt_token_rejects_wrong_issuer: real token minted with `iss` claim different from the configured issuer string used to select the JWKS client/cfg (simulate via mocked get_issuer_from_token returning the configured issuer while the signed payload's iss differs) -> real decode raises InvalidIssuerError -> 401. (AC #2)
  - test_validate_jwt_token_rejects_hs256_even_if_configured: issuer_config algorithms=['HS256'] (bypassing the settings-level guard by constructing JWKSManager directly, as today's tests already do); assert HTTPException 401 raised AND `jwks_client.get_signing_key_from_jwt` / `decode` are never called (algorithm filtering short-circuits before any decode attempt). (AC #3)
  - test_validate_jwt_token_filters_mixed_algorithms: issuer_config algorithms=['HS256','ES256']; a real ES256 token succeeds; assert (via mocked decode kwargs capture) that only ['ES256'] was passed. (AC #3, defense-in-depth)
  - test_validate_jwt_token_rejects_expired_token: real token with exp in the past -> ExpiredSignatureError -> 401. (AC #4)
  - test_validate_jwt_token_rejects_missing_exp_claim: real token minted without an exp claim -> MissingRequiredClaimError (from options.require) -> 401. (AC #4)
  - test_validate_jwt_token_rejects_future_nbf: real token with nbf in the future -> ImmatureSignatureError -> 401. (AC #4)
  - test_validate_jwt_token_missing_audience_in_config_rejected: issuer_config entry without 'audience' key (constructed directly, bypassing settings) -> 401 before any decode call. (defense-in-depth companion to AC #1)

AC-to-step-to-test traceability:
- AC #1 -> Step 1 (server.py model_validator) -> test_issuer_config_missing_audience_raises_validation_error, test_issuer_config_with_audience_is_valid.
- AC #2 -> Step 2 (issuer=/audience= passed) -> test_validate_jwt_token_passes_issuer_and_audience_to_decode, test_validate_jwt_token_rejects_wrong_audience, test_validate_jwt_token_rejects_wrong_issuer.
- AC #3 -> Step 2 (algorithm filtering) -> test_validate_jwt_token_rejects_hs256_even_if_configured, test_validate_jwt_token_filters_mixed_algorithms.
- AC #4 -> Step 2 (options require/verify_exp/verify_nbf) -> test_validate_jwt_token_rejects_expired_token, test_validate_jwt_token_rejects_missing_exp_claim, test_validate_jwt_token_rejects_future_nbf.
- Existing tests (test_validate_jwt_token_successful_validation and the rest of TestJWKSManager/TestValidateJWTToken) must still pass unmodified -- confirms no regression to the untrusted-issuer / missing-jwks_uri / missing-credentials paths above line 105.

Assumptions / doubts (resolved via human confirmation 2026-07-24):
- RESOLVED: real ISSUER_CONFIG entries already include 'audience' in every environment -- confirmed by the human reviewer. Dev uses app/.env with ISSUER_CONFIG='{\"http://127.0.0.1:8001\": {\"jwks_uri\": \"...\", \"algorithms\": [\"ES256\"], \"audience\": \"sre-bot-dev\"}}' (paired with app/bin/dev-token.py as the local fictitious JWKS/token server, which already mints tokens against that audience). Production's issuer config points at the Backstage instance -- the sole authenticated caller of these secure endpoints -- and that entry also carries an audience today. Step 1's boot-time requirement is therefore not expected to break any live environment; it only forecloses a config regression going forward.
- Assumes PyJWT 2.12.0 (pinned in app/pyproject.toml) options={'require': [...]} + verify_nbf/verify_exp behave as documented (confirmed via `uv run python -c 'import jwt; ...'`: decode() accepts issuer= as Container[str] | str | None).

Blast radius:
- Files touched: app/infrastructure/configuration/infrastructure/server.py, app/infrastructure/security/jwt.py (2 production files). Tests: app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py, app/tests/unit/infrastructure/security/test_jwt.py (+ possibly conftest.py fixture additions).
- Runtime effect: every JWT-protected route via get_current_user() (app/infrastructure/security/current_user.py) is affected -- strictly more restrictive validation (previously-accepted malformed/HS256/no-aud/no-iss/no-exp tokens now rejected with 401; well-formed tokens with a correctly configured asymmetric issuer -- dev's local ES256 JWKS server and prod's Backstage issuer, both already audience-bearing -- are unaffected).
- No schema/data migration; no API contract change (still 401 on auth failure); no change to dev-bypass path (current_user.py's DEV_BYPASS_TOKEN branch is untouched and does not call validate_jwt_token).

Rollback:
- Revert the two production files (and test files) in one commit; no state to unwind (settings validation and decode() options are stateless/in-process). Given the audience-present confirmation above, no operational config change is anticipated as a prerequisite to shipping this.

Single-PR size gate: fits easily (2 production files, ~40-60 production LOC, one subsystem -- security/auth; no decomposition needed).
<!-- SECTION:PLAN:END -->
