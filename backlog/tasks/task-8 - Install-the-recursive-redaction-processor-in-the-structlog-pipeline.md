---
id: TASK-8
title: Install the recursive redaction processor in the structlog pipeline
status: Done
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 23:21'
labels:
  - security
  - phase-0
  - observability
milestone: m-0
dependencies: []
references:
  - decisions/observability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1262'
priority: high
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/observability.md (Redaction). Today mask_sensitive_data exists at app/infrastructure/logging/formatters.py:64 but is NOT in the structlog processor chain (the processor list at app/infrastructure/logging/setup.py:168-204 omits it), and it does not recurse into nested dicts/lists (SEC-7, CWE-532).

Steps:
1. Make the redaction processor recursive: walk nested dicts and lists, replacing values whose keys match the deny-list (token, secret, password/passwd/pwd, authorization, api_key, credentials, signature, session*, *_token, ...) with ***REDACTED***.
2. Install it in the processor chain in app/infrastructure/logging/setup.py, positioned before the JSON renderer so it cannot be skipped per-call.
3. Add a redaction_extra_keys setting for extension.
4. Scope note: the full pipeline rework (foreign chain, UTC timestamps, logger names) is task-28; only redaction lands here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A log event containing {"config": {"api_token": "x"}} renders with ***REDACTED*** in place of the token value (pipeline test, not a unit test of the function alone)
- [x] #2 Deny-list keys are matched case-insensitively and in nested lists of dicts
- [x] #3 redaction_extra_keys extends the deny-list from settings (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass
- [x] #2 PR references SEC-7 and decisions/observability.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ground truth re-verified 2026-07-28 against current code (all line numbers below are live, not stale):

## Files touched (production, ~100 LOC / 5 files, single subsystem: infrastructure/logging + 1 wiring call site)

1. app/infrastructure/logging/formatters.py
   - SENSITIVE_PATTERNS (line 44-61): extend with "passwd", "pwd", "signature", "session", "passphrase" to match decisions/observability.md's literal catalogue ("password/passwd/pwd", "signature", "session*") and docs/adr/data-redaction-policy.md's table. NOT adding bare "sig" (docs/adr lists it but it is a high-false-positive substring - "design", "signal", "assign" all contain it); flagged below as a doubt for human sign-off. "credentials" plural needs no new entry: "credential" (already present) is a substring match, already catches it.
   - mask_sensitive_data() (line 64-92): make recursive. Add two small helpers: `_is_sensitive_key(key, patterns) -> bool` (the existing case-insensitive substring check, extracted) and `_redact_recursive(value, patterns, mask_value) -> Any` (if dict: rebuild dict, checking each key with `_is_sensitive_key` - if sensitive and non-None replace whole value with mask_value, else recurse into it; if list: map `_redact_recursive` over items; else: return unchanged). Rewrite `processor()`'s body to use `_is_sensitive_key`/`_redact_recursive` instead of the current flat loop. This preserves all existing top-level behavior (None passthrough, non-sensitive unchanged - existing tests keep passing unmodified) and additionally recurses into nested dict/list values under non-sensitive keys.

2. app/infrastructure/logging/setup.py
   - Extract the processor-list construction (current lines 166-194, ending right after `format_exc_info`) into a new module-level function `_build_base_processors(prod_mode: bool, logging_settings: LoggingSettings) -> list[Processor]` that returns the chain through exception formatting PLUS the redaction processor as its new last element: `mask_sensitive_data(additional_patterns=frozenset(logging_settings.REDACTION_EXTRA_KEYS))`. This is the test seam for AC#1 (see Test Matrix).
   - In `configure_logging` (line 105), add parameter `logging_settings: LoggingSettings | None = None`; if None, fetch `get_logging_settings()` internally (bootstrap-code exception to the "no get_settings() in constructors" rule - configure_logging already requires an explicit `AppSettings` and already defaults `log_level` internally from settings; flagged as a doubt below since this is a deliberate deviation kept optional specifically to avoid rewriting ~14 unrelated existing `configure_logging(settings=mock_settings)` call sites across app/tests/unit/infrastructure/test_logging.py and app/tests/unit/infrastructure/logging/test_setup.py that are out of this task's scope).
   - Replace the inline processors-list construction (lines 166-194) with `processors = _build_base_processors(prod_mode, logging_settings)`, then keep the existing dev/prod renderer branch (lines 196-201) appending ConsoleRenderer or JSONRenderer AFTER redaction - so redaction is installed once, ahead of BOTH renderer choices (broader than the task text's literal "before the JSON renderer" but required by decisions/observability.md's "cannot be skipped per-call" and the security intent; flagged below for confirmation).
   - Import `LoggingSettings, get_logging_settings` from the new settings module (see file 3).
   - The existing `_is_test_environment()` early-return branch (lines 135-158) is untouched - it never reaches the redaction processor, exactly as today (out of scope; task-28 owns the full pipeline/test-suppression rework).

3. app/infrastructure/logging/settings.py (NEW FILE, ~20 LOC)
   - Mirrors the existing `app/infrastructure/idempotency/settings.py` pattern exactly (confirmed precedent for infra-capability-owned partitioned settings, not just package-owned):
     ```python
     from functools import lru_cache
     from pydantic import Field
     from infrastructure.configuration.base import InfrastructureSettings

     class LoggingSettings(InfrastructureSettings):
         """Configuration for structured-logging redaction.

         Environment Variables:
             REDACTION_EXTRA_KEYS: JSON array of extra deny-list key substrings
                 (default: empty tuple). Matches the CORS_ALLOWED_ORIGINS
                 convention (terraform/ecs.tf:22 jsonencode()) for list-typed
                 settings from env vars.
         """
         REDACTION_EXTRA_KEYS: tuple[str, ...] = Field(default=(), alias="REDACTION_EXTRA_KEYS")

     @lru_cache(maxsize=1)
     def get_logging_settings() -> LoggingSettings:
         """Singleton provider for logging settings."""
         return LoggingSettings()
     ```

4. app/infrastructure/logging/__init__.py (line 57-63 imports, line 65-78 __all__)
   - Add `from infrastructure.logging.settings import LoggingSettings, get_logging_settings` and append both names to `__all__`, mirroring idempotency's `__init__.py` re-export convention.

5. app/server/lifespan.py
   - Line 59-60 `_get_logger_from_app(app_settings: AppSettings) -> BoundLogger`: add param `logging_settings: LoggingSettings | None = None` (default None -> internal `get_logging_settings()` fetch, same rationale as item 2) and forward it to `configure_logging(settings=app_settings, logging_settings=logging_settings)`.
   - Line 227 `lifespan()`: add `logging_settings = get_logging_settings()` alongside the other explicit settings fetches (app_settings/server_settings/directory_settings/sre_ops_settings at lines 223-226) and pass it: `logger = _get_logger_from_app(app_settings, logging_settings)` - for consistency with how every sibling settings slice is explicitly fetched in this function (not required for AC coverage, but avoids leaving this one fetch implicit next to four explicit ones).
   - Add the corresponding import from `infrastructure.logging.settings`.

## AC traceability

- AC#1 (nested `{"config": {"api_token": "x"}}` renders redacted, pipeline test): step 2's `_build_base_processors` is exercised end-to-end (contextvars merge -> log level -> timestamp -> callsite adder -> otel conventions -> exception formatting -> redaction) via `structlog.testing.capture_logs(processors=...)` in a NEW test `test_pipeline_redacts_nested_sensitive_value` in app/tests/unit/infrastructure/logging/test_setup.py. `capture_logs()`'s default behavior clears ALL configured processors unless you pass your own list explicitly (confirmed by reading the installed structlog 25.5.0 source) - so the test calls `_build_base_processors(prod_mode=True, logging_settings=LoggingSettings())` directly and passes that list to `capture_logs(processors=...)`, which appends its own capturing processor where the renderer would go. This is a real pipeline test (not a unit test of `mask_sensitive_data` alone) because it runs the actual ordered chain including callsite/otel/exception processors, not just the redaction function in isolation.
- AC#2 (case-insensitive, nested lists of dicts): new tests in app/tests/unit/infrastructure/logging/test_formatters.py's `TestMaskSensitiveData` - `test_mask_sensitive_data_recurses_into_nested_dict`, `test_mask_sensitive_data_recurses_into_list_of_dicts`, `test_mask_sensitive_data_recursion_is_case_insensitive_at_depth`.
- AC#3 (redaction_extra_keys extends the deny-list from settings): new file app/tests/unit/infrastructure/logging/test_settings.py (mirrors app/tests/unit/infrastructure/idempotency/test_idempotency_settings.py) - default-empty-tuple test, env-var JSON-array parsing test, singleton-provider test; PLUS one test in test_setup.py building `_build_base_processors(prod_mode=True, logging_settings=LoggingSettings(REDACTION_EXTRA_KEYS=("custom_secret",)))` and asserting a `custom_secret` key is redacted through `capture_logs` while defaults still apply too.

## Test matrix

| Case | File | Test |
| --- | --- | --- |
| Happy path: nested dict redacted through real pipeline | test_setup.py | test_pipeline_redacts_nested_sensitive_value |
| Nested dict (non-pipeline, direct function) | test_formatters.py | test_mask_sensitive_data_recurses_into_nested_dict |
| List of dicts | test_formatters.py | test_mask_sensitive_data_recurses_into_list_of_dicts |
| Case-insensitivity at depth | test_formatters.py | test_mask_sensitive_data_recursion_is_case_insensitive_at_depth |
| Deeply nested (dict-in-list-in-dict) boundary case | test_formatters.py | test_mask_sensitive_data_recurses_multiple_levels |
| Non-sensitive nested structures pass through unmodified | test_formatters.py | test_mask_sensitive_data_recursion_preserves_non_sensitive_nested |
| New deny-list entries (passwd, pwd, signature, session, passphrase) | test_formatters.py | test_mask_sensitive_data_masks_new_catalogue_patterns |
| Settings default (empty tuple) | test_settings.py | test_logging_settings_defaults_to_empty_extra_keys |
| Settings env parsing (JSON array) | test_settings.py | test_logging_settings_reads_redaction_extra_keys_from_env |
| Settings singleton | test_settings.py | test_get_logging_settings_returns_singleton |
| Extension applied through the real chain | test_setup.py | test_pipeline_redaction_extra_keys_extend_defaults |
| Registry: LoggingSettings instantiable as InfrastructureSettings | test_settings_structure.py | test_all_infrastructure_settings_classes_instantiable (extend existing list) |
| Existing behavior unchanged (regression) | test_formatters.py, test_setup.py | full existing TestMaskSensitiveData class + existing TestConfigureLogging class run unmodified |

## Assumptions and doubts (verify before/while implementing)

1. Assumes bare "sig" is deliberately excluded from the deny-list despite docs/adr/data-redaction-policy.md's table listing it, because it is a short, high-false-positive substring (matches "design", "signal", "assign", etc.). The task's own steps text and decisions/observability.md both list "signature" but not "sig" - verify: re-read decisions/observability.md line 18 (already done, confirms "signature" only) and ask the human reviewer to confirm "sig" stays excluded.
2. Assumes `logging_settings` should be an optional parameter (internal singleton fallback) on both `configure_logging` and `_get_logger_from_app`, rather than a strictly-required explicit parameter, to avoid a mechanical rewrite of ~14 out-of-scope existing call sites in app/tests/unit/infrastructure/test_logging.py and app/tests/unit/infrastructure/logging/test_setup.py (verified via repo-wide grep for `configure_logging(`). This is a narrow, justified exception to the settings-singleton skill's "no get_settings() in constructors" rule because `configure_logging`/`_get_logger_from_app` are bootstrap/factory functions, not service constructors, and the function already defaults `log_level` internally from settings today. Verify: confirm no reviewer objection to this pattern before merging.
3. Assumes the redaction processor should sit before BOTH the dev ConsoleRenderer and prod JSONRenderer (one processor, one position, applies regardless of environment) rather than literally "only before the JSON renderer" as the task text says - the decision record's "cannot be skipped per-call" intent and CWE-532/SEC-7 rationale apply equally to local/dev console output. Verify: confirm with human reviewer; if they want prod-only, the fix is a one-line move of the `mask_sensitive_data(...)` append into the `else` (prod) branch only.
4. Assumes `REDACTION_EXTRA_KEYS` env var format is a JSON array string (`["ssn","custom_secret"]`), matching the existing `CORS_ALLOWED_ORIGINS` convention (terraform/ecs.tf:22 `jsonencode(var.cors_allowed_origins)`), not a comma-separated string. Verify: no env var of this name exists yet in terraform/ or .env.example, so this is a fresh choice, not a migration - flag in PR description so ops knows the expected format when/if they ever set it.
5. Assumes no terraform/CI change is needed in this PR: REDACTION_EXTRA_KEYS defaults to an empty tuple (no behavior change if unset), so no new env var needs to exist in any deployment manifest before this ships (unlike TASK-6's TTL settings which needed a default already present in code). Verify: grep terraform/ecs.tf and terraform/templates/sre-bot.json.tpl found no existing REDACTION_EXTRA_KEYS entry - none is required for this PR to be safe to deploy.

## Blast radius and rollback

- Blast radius: every structlog log call in production/dev now passes through one additional processor (`mask_sensitive_data`) that only mutates values under keys matching the (extended) deny-list; all other fields pass through byte-for-byte. Risk is limited to: (a) a legitimate field whose key coincidentally matches a deny-list substring (e.g. a hypothetical `token_count` field) getting redacted when it shouldn't - mitigated by the deny-list being reviewed/scoped, and by AC#2's requirement that this is testable and visible; (b) minor CPU cost per log call from the recursive walk - bounded, same tradeoff docs/adr/data-redaction-policy.md already accepts.
- No consumer contract changes: `mask_sensitive_data()`'s public signature (`mask_value`, `additional_patterns`) is unchanged; only its internal behavior on nested structures changes (existing flat-dict tests keep passing since top-level behavior is preserved).
- `configure_logging`/`_get_logger_from_app` gain a new optional trailing parameter with a safe internal default - zero-behavior-change for every existing caller that does not pass it.
- Single `git revert` of this PR fully restores prior behavior (redaction absent from the chain, non-recursive masking) with no follow-up cleanup required - no data migration, no manifest/env var must exist first, no straddling old/new paths.
- Ordering constraint: none. This PR is fully self-contained; TASK-28 (full pipeline rework: foreign chain, UTC timestamps, logger names) is explicitly out of scope and unblocked either way.

## Size-gate verdict

Estimated production diff: ~100 LOC across 5 files (formatters.py, setup.py, settings.py [new], __init__.py, lifespan.py), one subsystem (infrastructure/logging + its one wiring call site in server/lifespan.py). No terraform/CI change required. Not mixing an unrelated mechanical refactor with the behavior change (the one extraction - `_build_base_processors` - exists solely to make the new behavior testable, not a repo-wide rename). Single git revert safely restores prior behavior. **Fits one PR - no decomposition needed.**
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Implementation Complete

### What Changed

**Production Code (~100 LOC, single subsystem):**

1. **app/infrastructure/logging/formatters.py** (~30 LOC added):
   - Extended SENSITIVE_PATTERNS with passwd, pwd, passphrase, signature, session (matches decisions/observability.md and docs/adr/data-redaction-policy.md)
   - Added _is_sensitive_key() helper for case-insensitive key matching (extracted from existing logic)
   - Added _redact_recursive() helper to walk nested dicts/lists, replacing values under sensitive keys with ***REDACTED*** (satisfies SEC-7, CWE-532)
   - Modified mask_sensitive_data() processor to use recursive helpers; all top-level behavior unchanged (existing tests pass unmodified)

2. **app/infrastructure/logging/setup.py** (~25 LOC added):
   - New _build_base_processors(prod_mode, logging_settings) factory function returns full processor chain through exception formatting + redaction processor (test seam for AC#1)
   - Added logging_settings: LoggingSettings | None optional parameter to configure_logging() with internal singleton fallback
   - Processor chain now includes redaction BEFORE final renderer (ConsoleRenderer or JSONRenderer), ensuring it runs in all environments

3. **app/infrastructure/logging/settings.py** (NEW FILE, ~20 LOC):
   - New LoggingSettings class (InfrastructureSettings subclass) with REDACTION_EXTRA_KEYS tuple field
   - Mirrors idempotency/settings.py pattern for partitioned infrastructure settings
   - get_logging_settings() singleton provider with lru_cache

4. **app/infrastructure/logging/__init__.py** (~5 LOC):
   - Re-exported LoggingSettings and get_logging_settings from new settings module

5. **app/server/lifespan.py** (~10 LOC):
   - Added logging_settings parameter (with internal singleton fallback) to _get_logger_from_app()
   - Explicit logging_settings fetch in lifespan() alongside other settings slices, forwarded to _get_logger_from_app()

### Test Evidence (All 3 ACs Verified)

AC#1 - Pipeline integration test: logs {"config": {"api_token": "x"}} through real processor chain, verifies token redacted. PASSED

AC#2 - Case-insensitive nested recursion: test_mask_sensitive_data_recurses_into_nested_dict, test_mask_sensitive_data_recurses_into_list_of_dicts, test_mask_sensitive_data_recursion_is_case_insensitive_at_depth, test_mask_sensitive_data_recurses_multiple_levels, test_mask_sensitive_data_masks_new_catalogue_patterns all PASSED

AC#3 - Settings extension: test_logging_settings_defaults_to_empty_extra_keys, test_logging_settings_reads_redaction_extra_keys_from_env, test_get_logging_settings_returns_singleton, test_pipeline_redaction_extra_keys_extend_defaults, test_all_infrastructure_settings_classes_instantiable all PASSED

Full test run: 61/61 passed (all logging/settings/structure tests green; plus fixed integration test test_lifespan_get_logger_configures_logging)

### DoD Verification (for human review)

- Tests pass (61 unit + integration tests verified)
- PR will reference SEC-7 and decisions/observability.md (ready for commit message)
- Deployment: REDACTION_EXTRA_KEYS defaults to empty tuple (no env var setup required before deploy) - no terraform/CI changes needed
- Lifespan wiring: optional logging_settings param introduced as justified bootstrap exception; all existing configure_logging() call sites work unchanged (no mechanical refactor of ~14 test fixtures required)

### Scope Confirmation

Per approved plan: scope limited to redaction processor recursive walk + settings wiring + pipeline chain installation. Full pipeline rework (foreign chain, UTC timestamps, logger names) is TASK-28 (out of scope, unblocked).
<!-- SECTION:NOTES:END -->
