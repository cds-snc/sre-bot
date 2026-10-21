---
id: TASK-111.2
title: >-
  Load settings from base and per-environment TOML files through a contracts
  settings base and a host loader
status: In Progress
assignee:
  - '@me'
created_date: '2026-10-20 23:25'
updated_date: '2026-10-21 13:28'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.1
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1749'
parent_task_id: TASK-111
type: feature
ordinal: 408000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pydantic-settings >= 2.15 (toml_table_header). contracts/configuration.py holds the settings-slice base (each slice names its table) and the Protocol that supplies the file list; server/configuration/ implements it: file selection from ENVIRONMENT, base then <environment>.toml, deep merge, existence check, registered in lifespan's configuration phase before any slice builds. app/config/{base,local,ci,production}.toml ship in the image. LoggingSettings is the first slice on it and gains log_level from AppSettings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 pydantic-settings is pinned to a release >= 2.15 and the lock file is updated
- [x] #2 A slice built on the contracts base reads its own table from base.toml deep-merged with <ENVIRONMENT>.toml; an environment variable overrides a file value and a file value overrides the code default
- [x] #3 A missing base or environment file, malformed TOML, a non-table value or an unknown key in a slice's table fails boot with a message naming the file, table and key
- [x] #4 app/config holds base.toml and one file per ENVIRONMENT value; a test fails when an ENVIRONMENT value has no file or a file does not parse
- [x] #5 LoggingSettings reads [logging] (log_level, redaction_extra_keys) from the files; production log output is unchanged
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #7 Building a slice on the contracts base before the configuration phase installs the files fails with an error naming the slice
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (2026-10-21 planning, human): the host installs the loaded files once into contracts/configuration.py and a slice built before that fails closed (ConfigurationError naming the slice); contracts/ may import pydantic-settings for the slice base (plugin-architecture.md, 2026-10-20), and import-linter contracts (c) and (l) allow it. Lock resolves pydantic-settings 2.16.1 (pyproject >=2.15.0); every probe below was re-run on 2.15.0 and 2.16.1 with the same result.

Probed behaviour the loader closes (pydantic-settings alone): a missing file is silently skipped; malformed TOML raises TOMLDecodeError without the file name; a non-table top-level value raises AttributeError; an unknown key raises ValidationError naming the key but not the file or table; a table absent from every file raises KeyError; an upper-case TOML key is silently ignored under case_sensitive=False even with extra=forbid.

Steps
1. app/pyproject.toml: pydantic-settings>=2.15.0; uv lock --upgrade-package pydantic-settings (2.13.1 -> 2.16.1). (AC1)
2. contracts/configuration.py (new):
   - ConfigurationError(Exception), message names file, table and key where known.
   - ConfigurationFiles Protocol: paths() -> tuple[Path, ...] (base first, then the environment file), environment name for messages.
   - install_configuration_files(files) / the installed slot; re-install replaces (lifespan runs more than once under test).
   - ConfigurationSlice(BaseSettings): model_config env_file=".env", case_sensitive=False, extra="forbid", env_nested_delimiter="__"; each slice sets toml_table_header=("<table>",) and env_prefix="<TABLE>__", and __init_subclass__ rejects a mismatch between them. settings_customise_sources: init, env, dotenv, TomlConfigSettingsSource(paths, deep_merge=True), file secrets (ADR order). Building with no files installed raises ConfigurationError naming the slice. The slice's table must be in base.toml (ADR: base holds defaults for every slice), else ConfigurationError naming base.toml and the table (replaces the KeyError). A ValidationError whose first loc is a key in the slice's table re-raises as ConfigurationError naming the last file that sets it, the table and the key (unknown key, bad type); other errors propagate unchanged.
3. server/configuration/__init__.py and loader.py (new): TomlConfigurationFiles implementing the Protocol; load_configuration_files(environment, directory=app/config) checks both files exist, parses each with tomllib (TOMLDecodeError -> ConfigurationError naming file and line), every top-level value is a table (names file and key), every key in a table is lower snake_case (names file, table, key; closes the silent upper-case case).
4. app/config/base.toml ([logging] log_level = "INFO", redaction_extra_keys = []), local.toml, ci.toml, production.toml (no overrides; header comment only). The Dockerfile COPY app/ already ships them; .dockerignore does not exclude them.
5. infrastructure/logging/settings.py: LoggingSettings(ConfigurationSlice), table logging, env_prefix LOGGING__, fields log_level: str = "INFO" and redaction_extra_keys: tuple[str, ...] = (), no alias. Lower-cased here because the file keys are lower case; 111.5 drops LoggingSettings. Env names become LOGGING__LOG_LEVEL and LOGGING__REDACTION_EXTRA_KEYS; production sets neither (doc-14), so no deployment-side rename.
6. infrastructure/configuration/app.py: drop LOG_LEVEL. infrastructure/logging/setup.py:235: effective level = log_level argument or logging_settings.log_level (docstring :156). server/lifespan.py: configuration phase first: get_app_settings(), install_configuration_files(load_configuration_files(ENVIRONMENT)), then the slices; logger.info("configuration_loaded", phase="configuration", files=[names]) once the logger exists; _list_configs_from_sections reads log_level from LoggingSettings (:89).
7. Makefile debug target: LOGGING__LOG_LEVEL=DEBUG. .env.example: rename LOG_LEVEL / REDACTION_EXTRA_KEYS if present (the file is permission-blocked for the agent; check at implementation).
8. decisions/configuration.md: Context notes LoggingSettings as the first slice on the files; dated Changes entry (2026-10-21, TASK-111.2: fail-closed install, table required in base.toml, lower-case key check).
9. Tests: root conftest session fixture installs the ci files (pytest-env sets ENVIRONMENT=ci); readers of AppSettings.LOG_LEVEL updated (tests/unit/infrastructure/conftest.py:14, tests/unit/infrastructure/logging/conftest.py:14, test_app_settings.py:16,31, tests/integration/test_app_state_initialization.py:51); tests/unit/infrastructure/logging/test_settings.py and test_settings_structure.py:121 edited in place (LoggingSettings is no longer an InfrastructureSettings).

Test matrix (TDD, failing first)
- tests/unit/contracts/test_contracts_configuration_slice_load.py: base then env file deep merge; env var beats file, file beats default (AC2); uninstalled build fails naming the slice (AC7); unknown key and bad type name file/table/key; table missing from base.toml fails; prefix/table mismatch rejected at class creation.
- tests/unit/server/configuration/test_server_configuration_files_load.py: missing base, missing environment file, malformed TOML (file and line), non-table value, upper-case key (AC3).
- tests/unit/server/configuration/test_server_configuration_files_present.py: every ENVIRONMENT Literal value has a file and every file in app/config parses through the loader (AC4).
- tests/unit/infrastructure/logging/test_settings.py: [logging] values read; LOGGING__ env overrides; production files give INFO and no extra keys (AC5).
- tests/unit/infrastructure/logging/test_setup.py: root level comes from LoggingSettings.log_level; explicit log_level argument still wins (AC5).
- tests/integration/server/test_server_lifespan_configuration_phase.py: real lifespan with later phases stubbed (pattern of test_lifespan_vendor_slice_validation.py): unknown key in a temp [logging] fails boot before yield naming file, table, key; missing environment file fails boot; valid files boot and log configuration_loaded with both names (AC3).

AC -> step: AC1 s1; AC2 s2,s4,s5; AC3 s2,s3,s6; AC4 s3,s4; AC5 s4,s5,s6; AC6 gates; AC7 s2,s6,s9.

Gates: ruff; mypy (0 in touched files); pytest tests --ignore=tests/smoke; make check-import-contracts; make check-settings-key-ownership; make lock-check.

Size: ~250 production LOC, ~11 files plus four config files and the lock, one subsystem (configuration). Within the gate.

Assumptions and doubts
- No slice on the base is built at import time: logging is configured only in lifespan (setup.py:201, lifespan.py:72,249); verified by the fail-closed test suite.
- Developer .env files may still set LOG_LEVEL; it is ignored after this change (make debug shows the new name).
- extra=forbid with env_file=".env" only rejects LOGGING__-prefixed unknown names; verify with a test.

Blast radius and rollback: a bad or missing file, or an unknown [logging] key, fails boot before yield; the ECS circuit breaker rolls back to the previous revision, which reads no file. Production log level and redaction stay at their defaults. One git revert restores service; no deployment-side step.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-21 implementation (plan unchanged after reviewing d982aa58 / #1762: it adds the Socket Mode downgrade processor to the stdlib chain and touches no settings).

What changed
- app/pyproject.toml pydantic-settings>=2.15.0; uv.lock 2.13.1 -> 2.16.1.
- contracts/configuration.py (new): ConfigurationError; ConfigurationFiles Protocol (environment and paths attributes, base file first); install/uninstall/installed_configuration_files; ConfigurationSlice base (env_file .env, case_sensitive=False, extra=forbid, env_nested_delimiter "__"). A subclass must name one table in toml_table_header and set env_prefix "<TABLE>__" (TypeError at class creation otherwise). Sources: init, env, .env (own fields only), TomlConfigSettingsSource(deep_merge=True), file secrets. Building with nothing installed fails naming the slice; a table missing from base.toml fails naming the file and table; a ValidationError on a key a file sets re-raises as ConfigurationError naming the last such file, the table and the key.
- Deviation from the plan, found by the gates: pydantic-settings 2.16 under extra=forbid reports every non-empty .env key, including other slices' unprefixed names, as an extra input. The base wraps the dotenv source to pass on only the slice's own fields, so extra=forbid guards the table. A misspelled LOGGING__ name in .env is ignored, as it is in the process environment. Recorded in decisions/configuration.md.
- server/configuration/ (new): load_configuration_files(environment, directory=None) returns TomlConfigurationFiles(base.toml, <environment>.toml) from app/config after checking that each file exists, parses (tomllib message keeps the line), has only tables at the top level, and uses lower snake_case table and key names. This closes pydantic-settings' silent skip of upper-case keys.
- app/config/base.toml ([logging] log_level = "INFO", redaction_extra_keys = []); local.toml, ci.toml and production.toml hold no overrides yet.
- LoggingSettings is on the base: [logging] log_level and redaction_extra_keys, env LOGGING__LOG_LEVEL and LOGGING__REDACTION_EXTRA_KEYS, no alias. AppSettings.LOG_LEVEL is removed. configure_logging takes its level from the logging slice; the log_level argument still overrides it.
- server/lifespan.py: the configuration phase first loads and installs the files for AppSettings.ENVIRONMENT, then builds the slices. It logs configuration_files_loaded (phase=configuration, environment, file names). _list_configs_from_sections takes the logging slice for LOG_LEVEL; TASK-156 replaces it.
- Makefile debug target sets LOGGING__LOG_LEVEL=DEBUG. The Dockerfile's COPY app/ ships app/config.
- decisions/configuration.md: Context updated; 2026-10-21 Changes entry.
- Tests: root conftest installs the ci files before every test (loaded once per session). New: tests/unit/contracts/test_contracts_configuration_slice_load.py (10), tests/unit/server/configuration/test_server_configuration_files_load.py and test_server_configuration_files_present.py, tests/integration/server/test_server_lifespan_configuration_phase.py (3). Edited in place: the logging settings and setup tests, the LOG_LEVEL mocks, test_app_settings, test_settings_structure, test_app_state_initialization, test_lifespan.

Evidence (from app/)
- uv run ruff check . -> All checks passed; ruff format --check -> 995 files already formatted.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> 47 errors in 18 files, 0 in touched files (all in untouched modules/, i18n, resilience, slack channels, docs_generator).
- uv run pytest tests --ignore=tests/smoke -> 5488 passed.
- make check-import-contracts -> 12 kept, 0 broken; make check-settings-key-ownership -> OK; make lock-check -> OK.

For the human
- Production sets neither LOG_LEVEL nor REDACTION_EXTRA_KEYS (doc-14), so no deployment-side rename is needed, and production logging stays INFO with the default redaction list.
- app/.env.example could not be read by the agent (permission rule). If it names LOG_LEVEL or REDACTION_EXTRA_KEYS, rename them to LOGGING__LOG_LEVEL and LOGGING__REDACTION_EXTRA_KEYS. A developer .env that sets LOG_LEVEL is now ignored.
<!-- SECTION:NOTES:END -->
