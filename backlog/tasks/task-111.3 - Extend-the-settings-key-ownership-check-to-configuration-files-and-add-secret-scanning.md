---
id: TASK-111.3
title: Extend the settings key ownership check to configuration-file tables
status: Done
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-21 16:34'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - app/bin/check_settings_key_ownership.py
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1750'
parent_task_id: TASK-111
type: feature
ordinal: 409000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
bin/check_settings_key_ownership.py gains a config-file claim source: each table in app/config/*.toml is claimed by the slice whose model_config names it in toml_table_header; a table no slice owns, or one table named by two slices, fails; a ConfigurationSlice reads only its <TABLE>__ names or a platform-provided name, and never an SDK or runtime namespace name (AWS_*, UVICORN_*, OTEL_*). Secret leaks are left to GitHub secret scanning and to developers; this task adds no secret scanner and no secret-shaped key rule.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 bin/check_settings_key_ownership.py claims each settings slice's toml_table_header table as a config-table claim; two slices naming one table fail naming both owners, and a non-literal toml_table_header fails as unreadable
- [x] #2 Every top-level table in app/config/*.toml is claimed by a slice, and every claimed table is in base.toml; an unowned table fails naming the file and table, a missing one names the slice
- [x] #3 A ConfigurationSlice reads only <TABLE>__ names or a platform-provided name (ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS); a name in the SDK and runtime namespaces (AWS_*, UVICORN_*, OTEL_*) fails as SDK-read; legacy BaseSettings slices are untouched until they move onto the files
- [x] #4 decisions/configuration.md Checks and Changes record the table and allow-list rules, and replace the secret-shaped key and gitleaks check with GitHub secret scanning plus developer responsibility
- [x] #5 ruff, mypy (0 errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (pending approval, 2026-10-21):
- No secret scanner and no secret-shaped key rule (human, 2026-10-21). GitHub secret scanning covers the public repository, and developers stay responsible for keeping secrets out of code and configuration. The ADR's gitleaks and secret-shaped key check is replaced, not deferred. A gitleaks trial over the full history found 20 hits, all test fixtures or doc examples, which shows the false-positive cost a second scanner would add.
- Allow-list: slice-side only. A ConfigurationSlice reads only <TABLE>__ names or a platform-provided name; an SDK or runtime namespace name (AWS_ then a non-underscore, UVICORN_, OTEL_) fails because the SDK reads it itself. Deployment-side names (terraform, workflows) are not scanned: renames publish names with no reader during the parallel change, so that check belongs to the contract step, TASK-111.15.

Steps:
1. Tests first, in app/tests/unit/bin/test_bin_settings_key_ownership_check.py (extended in place; tmp_path trees with an app/config directory):
   a. table claimed by two slices -> key-ownership violation naming both owners (AC1);
   b. toml_table_header not a literal tuple of one string -> unreadable (AC1);
   c. table in local.toml no slice owns -> unowned-table naming file and table; slice table absent from base.toml -> missing-table naming the slice; nested [slack.tenant] counts as the slack table (AC2);
   d. ConfigurationSlice with a validation_alias SLACK_BOT_TOKEN -> env-naming; alias AWS_REGION -> sdk-namespace; a slice whose prefix is AWS__ passes; legacy BaseSettings reading AWS_REGION passes; a slice reading ENVIRONMENT passes (AC3);
   e. real tree: [logging] claimed by infrastructure.logging.settings:LoggingSettings; still clean (AC1-3).
2. app/bin/check_settings_key_ownership.py:
   - CONFIG_KEYS gains toml_table_header, read as a literal tuple of string constants (else _Unreadable);
   - TABLE_SOURCE = "config-table" claims per settings class with a header; find_collisions covers them unchanged;
   - _Tree.is_configuration_slice(cls): base chain reaches (contracts.configuration, ConfigurationSlice);
   - find_violations(root) reads root/config/*.toml with tomllib: unowned-table, missing-table;
   - PLATFORM_NAMES = ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS; SDK namespace pattern; env-naming and sdk-namespace rules over ConfigurationSlice env claims;
   - module docstring and the OK/FAIL messages name the new rules.
3. decisions/configuration.md: Checks bullets for the table rules and the slice-side allow-list; the secret bullet becomes GitHub secret scanning plus developer responsibility; a 2026-10-21 Changes entry for TASK-111.3.
4. Gates from app/: ruff, mypy (touched files), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.

AC traceability: AC1 1a, 1b, 1e -> 2; AC2 1c, 1e -> 2; AC3 1d -> 2; AC4 -> 3; AC5 -> 4.

Size: about 90 production LOC in the script, ADR text, about 150 test LOC; 3 files, one subsystem (CI checks). Within the gate.

Blast radius and rollback: CI-only, nothing ships to the runtime. A false positive blocks merges until the rule is adjusted; one git revert removes it.

Approved 2026-10-21.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-21: implemented. bin/check_settings_key_ownership.py claims each slice's toml_table_header as a config-table claim (toml_table_header read as a literal tuple; non-literal -> unreadable-alias), so two slices naming one table collide through the shared find_collisions. New rules: unowned-table (a table in config/*.toml no slice names), missing-table (a slice's table absent from base.toml), invalid-config (unparseable file), env-naming and sdk-namespace (ConfigurationSlice subclasses only, found by base chain to contracts.configuration:ConfigurationSlice; PLATFORM_NAMES ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS allowed bare; SDK pattern (AWS|UVICORN|OTEL)_ then a non-underscore, so an AWS__ table prefix passes). collect_claims returns env and table claims; collect_env_claims keeps returning env claims only; vendor-enabled reads env claims only. Real tree: LoggingSettings is the one configuration slice and claims [logging]; tree clean. Tests: 14 new cases in tests/unit/bin/test_bin_settings_key_ownership_check.py, LoggingSettings added to the pydantic parity test. ADR: Checks bullets rewritten (GitHub secret scanning replaces gitleaks and the secret-shaped key rule, human 2026-10-21), 2026-10-21 TASK-111.3 Changes entry. Gates: ruff clean; ruff format clean; mypy 47 errors in 18 files, 0 in touched files; pytest tests --ignore=tests/smoke 5502 passed; make check-import-contracts 12 kept, 0 broken; make check-settings-key-ownership OK.
<!-- SECTION:NOTES:END -->
