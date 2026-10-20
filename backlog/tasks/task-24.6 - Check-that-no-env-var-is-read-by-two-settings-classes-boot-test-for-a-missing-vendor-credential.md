---
id: TASK-24.6
title: >-
  Check that no env var is read by two settings classes; boot test for a missing
  vendor credential
status: Done
assignee:
  - '@me'
created_date: '2026-10-19 17:19'
updated_date: '2026-10-20 21:27'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies:
  - TASK-24.1
  - TASK-24.2
  - TASK-24.5
references:
  - decisions/configuration.md
  - decisions/plugins.md
parent_task_id: TASK-24
priority: medium
ordinal: 404000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 6 of TASK-24, its contract. decisions/configuration.md Checks: each key is owned by exactly one settings slice; a vendor slice with a tenant entry missing a secret fails boot naming the key; no <VENDOR>_ENABLED field in integrations/ (SLACK_ENABLED excepted until TASK-112).

- A CI check (app/bin script, run by the CI workflow) collects every BaseSettings subclass under app/ and fails when one environment variable name is read by two classes. TASK-111 extends it to configuration-file keys.
- A boot test extends tests/integration/server/test_lifespan_vendor_slice_validation.py: a missing required vendor credential fails boot with a message naming the variable.
After this slice TASK-24's umbrella ACs are verifiable and TASK-111 can start.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An app/bin script, run by the CI workflow through a Makefile target, fails naming both owning classes when one environment variable name is read by two BaseSettings classes under app/ (tests excluded), and passes on main; it records each claim as (source kind, key, owning class) so TASK-111 adds configuration-file keys as a second claim source
- [x] #2 A missing required vendor credential fails boot naming the variable: covered by the two existing tests in tests/integration/server/test_lifespan_vendor_slice_validation.py (Slack transport on without SLACK_TEAM_ID; Google GOOGLE_WORKSPACE_CUSTOMER_ID without GCP_SRE_SERVICE_ACCOUNT_KEY_FILE), the only vendor slices with a tenant entry; this task adds no boot test
- [x] #3 The same script fails when a field in an app/integrations settings module is named or aliased <VENDOR>_ENABLED (or ENABLED outside the Slack module) other than SLACK_ENABLED, and passes on main; the exception is removed with TASK-112
- [x] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #5 The same script fails on an os.environ or os.getenv read in app/ outside a settings class body (bin/ and tests/ excluded), and passes on main
- [x] #6 decisions/configuration.md records that environment names are upper case and matched exactly by each slice, and that key ownership treats names differing only by case as one key
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Size: 4 production files (app/bin/check_settings_key_ownership.py ~240 LOC, app/Makefile +3, .github/workflows/ci_code.yml +4, decisions/configuration.md +2 lines), one subsystem (CI tooling) plus the ADR line the check enforces. Gate: pass. Tests excluded from the count.

Findings (grounded)
- Settings classes under app/ (34 incl. bases; none under app/modules): features/incident/{common,comms,scribe}, infrastructure/{audit,configuration/*,coordination,directory,drive,logging,security,slack,spreadsheets}, integrations/<vendor>/settings.py, packages/access/common/settings.py, and one function-local class, EnvConfigLoader._EnvModel (packages/access/common/config/loaders.py:248). Import-based discovery cannot see the local class and would import settings modules with side effects; AST discovery sees both and matches every sibling script in app/bin.
- Name derivation (pydantic-settings): alias string wins, else env_prefix + field name; validation_alias/AliasChoices/AliasPath are unused in app/ code; case_sensitive=False folds to lowercase (AppSettings, AccessSettings); populate_by_name adds the bare field name (infrastructure/slack/settings.py:20 so COMMAND_PREFIX is also read); AccessSettings (packages/access/common/settings.py:132) uses env_prefix ACCESS_, env_nested_delimiter _, env_nested_max_split 1 over BaseModel sub-slices, so ACCESS_SYNC_ENABLED etc. are nested names.
- Duplicates on main: none. A prototype derivation over all 34 classes (case-folded across classes) found zero shared names, so no fix is needed and no baseline file is needed (like check_runtime_imports).
- <VENDOR>_ENABLED in app/integrations: only SLACK_ENABLED (integrations/slack/settings.py:59).
- CI runs app/bin scripts as Makefile targets (app/Makefile:98-114, ci_code.yml steps 48-68), each with a tests/unit/bin/test_bin_<x>_check.py that also asserts the Makefile and workflow wiring.
- AC2 is already satisfied: tests/integration/server/test_lifespan_vendor_slice_validation.py has the Slack (SLACK_TEAM_ID) and Google (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE) cases; Slack and Google are the only integrations with a tenant entry, so there is nothing further to parametrize.

Steps
1. app/bin/check_settings_key_ownership.py (AST only, reuse bin.freeze_guard.iter_python_files with "tests" excluded):
   a. Index every ClassDef (including nested) by name; a class is a settings class when its base chain, resolved by name across the tree, reaches BaseSettings. Collect SettingsConfigDict(...) literals (env_prefix, case_sensitive, env_nested_delimiter, env_nested_max_split, populate_by_name/validate_by_name) with inheritance from bases (FeatureSettings, InfrastructureSettings).
   b. Derive claims per field declared on the class itself (inherited fields are not re-claimed by subclasses): Field(alias=...) literal, every literal in validation_alias (a string or AliasChoices(...) of strings; TASK-111 AC7 reads old names this way for one release, and each one is a key the class reads) else prefix+name; aliases are claimed without env_prefix (pydantic-settings env_prefix_target default "variable" applies the prefix to field names only); add the bare name when populate_by_name; nested BaseModel annotations expand to prefix+field+delimiter+subfield (and the top-level name for JSON). A non-literal alias, an AliasPath or non-string AliasChoices entry, or an unresolvable model_config raises a failure naming the class, never a silent skip.
   c. Claim = frozen dataclass (source_kind="env", key, owner "<module>:<Class>"); find_collisions(claims) groups by (source_kind, folded key) and reports keys with two or more distinct owners. TASK-111 adds a "config-file" claim collector and reuses find_collisions unchanged.
   d. Second rule vendor-enabled: in app/integrations/*/settings.py a field named ENABLED or whose name/alias ends _ENABLED fails unless the alias is in ALLOWED_ENABLED = {"SLACK_ENABLED"} (comment: remove with TASK-112).
   e. Third rule environ-read: a call or subscript of os.environ / os.getenv / os.environ.get under app/ fails unless it sits inside a settings class body; bin/ (developer scripts such as bin/dev-token.py) and tests/ are excluded. decisions/configuration.md Checks: "no os.environ reads outside settings classes"; passes on main (only bin/dev-token.py reads it today).
   f. main(): print violations, exit 1; usage line python3 -m bin.check_settings_key_ownership.
1g. decisions/configuration.md: under "Environment names mirror the configuration path" add that environment names are upper case and each slice matches them exactly (case_sensitive=True, the convention TASK-24.1 and 24.2 set), and that key ownership treats names differing only by case as one key, because pydantic-settings matches case-insensitively by default, always on Windows, and for aliases; cite POSIX XBD chapter 8 and pydantic-settings; add a dated Changes line (TASK-24.6). Checks: the CI line names the script.
2. app/Makefile: target check-settings-key-ownership (uv run python -m bin.check_settings_key_ownership).
3. .github/workflows/ci_code.yml: step "Settings key ownership check" (working-directory ./app, run make check-settings-key-ownership) before the Test step.
4. Tests (written first, TDD): app/tests/unit/bin/test_bin_settings_key_ownership_check.py.

Test matrix (AC traceability)
- AC1: two classes with the same alias fail naming both; same alias differing only by case across a case-insensitive class fails; prefix+field collision fails; shared alias in one class only passes; subclass inheriting a field is not a duplicate; nested model expansion yields ACCESS_SYNC_ENABLED style names and collides with a flat alias; populate_by_name adds the bare name; function-local settings class is found; non-literal alias fails loudly; tests/ tree ignored; parity test against the real classes (explicit top-level imports of SlackSettings, SlackTransportSettings, AppSettings, AccessSettings, SecuritySettings) comparing AST-derived names to the model aliases/field names; real tree reports clean; Makefile target and ci_code.yml step exist.
- AC2: no new test; run the two existing boot tests and cite output in notes.
- AC1 (aliases): validation_alias string and AliasChoices strings are claimed and collide with another class's name; an alias is claimed without the class env_prefix; AliasPath or a non-literal entry fails loudly.
- AC5: os.environ[...] / os.environ.get / os.getenv in a non-settings module fails; the same read inside a settings class body passes; bin/ and tests/ trees are ignored; real tree clean.
- AC6: doc-only, reviewed in the PR.
- AC3: SLACK_ENABLED allowed; OPSGENIE_ENABLED-style field and bare ENABLED in a non-Slack integration fail; real tree clean.
- AC4: ruff, mypy on the two touched Python files, pytest tests --ignore=tests/smoke.

Assumptions and doubts
- No other code reads env keys outside BaseSettings classes in app/ (os.environ reads are a separate ADR grep check, not this task): verify with rg os.environ app --glob '!tests'.
- Literal-only aliases hold for all new settings: enforced by the loud-failure rule.
- AST derivation matches pydantic-settings for nested models: verified by the parity test on AccessSettings.

Blast radius and rollback: CI-only addition; a false positive blocks PRs but a git revert of the three files restores CI. No runtime code touched. Env names are folded to lowercase across all classes (decision 2026-10-20 from research: POSIX keeps case distinct and reserves lower case for applications, but pydantic-settings folds by default, on Windows and for aliases, and ASP.NET Core configuration keys are case-insensitive, so a case-only difference is one key for ownership). AST discovery follows pyflakes and import-linter practice (parse, never import, so modules with import side effects are safe).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- New app/bin/check_settings_key_ownership.py: AST-only guard (never imports the scanned code) over app/ minus tests/, with three rules from decisions/configuration.md Checks:
  - key-ownership: each environment key a BaseSettings class reads is a Claim(source_kind="env", key folded to lower case, owner "<module>:<qualname>"). find_collisions groups by (source kind, key) and fails naming every owner. Names follow pydantic-settings: alias / validation_alias / each AliasChoices string read without env_prefix; otherwise env_prefix + field name; populate_by_name or validate_by_name also claims the field name; nested model fields expand by env_nested_delimiter, bounded by env_nested_max_split; config is inherited from base classes. Base classes are resolved through imports and re-exports, so FeatureSettings/InfrastructureSettings subclasses and the nested EnvConfigLoader._EnvModel are seen (34 classes, 158 keys on main).
  - unreadable-alias: an AliasPath, a non-literal alias or a non-literal model_config fails loudly instead of being skipped.
  - vendor-enabled: a key ENABLED or *_ENABLED read by a class under integrations/ fails, except ALLOWED_VENDOR_SWITCHES = {"SLACK_ENABLED"} (TASK-112 AC #6 empties it).
  - environ-read: os.environ / os.environb / os.getenv access, or from os import environ/getenv, outside a settings class body fails; bin/ and tests/ are exempt (only bin/dev-token.py reads the environment today).
- app/Makefile: check-settings-key-ownership target (and .PHONY); .github/workflows/ci_code.yml: "Settings key ownership check" step after the fake-coverage check, before Test.
- decisions/configuration.md: environment names are upper case and matched exactly by each slice (case_sensitive=True); ownership compares case-insensitively (POSIX XBD 8.1; pydantic-settings folds by default, on Windows and for aliases). Checks: the CI line names the script; the vendor-switch and os.environ lines are now CI checks; "no environment derivation outside ENVIRONMENT" stays a grep check. Dated Changes line.
- AC2: no new boot test; the existing Slack (SLACK_TEAM_ID) and Google (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE) cases in tests/integration/server/test_lifespan_vendor_slice_validation.py cover the only two vendor slices with a tenant entry.

Tests
- New tests/unit/bin/test_bin_settings_key_ownership_check.py (30 tests): collisions across classes, case folding, prefix vs alias, alias without prefix, same class twice, inherited field and config, nested expansion and nested-vs-flat collision, populate_by_name, AliasChoices/validation_alias claims, AliasPath and non-literal aliases fail, nested class found, ClassVar/private/BaseModel ignored, tests/ ignored, vendor rule (prefixed and bare ENABLED fail, SLACK_ENABLED allowed, non-integrations ignored), environ rule (three spellings with lines, from-import, inside settings class passes, bin/ and tests/ exempt), source-kind grouping, parity with pydantic for SlackSettings, SlackTransportSettings, AppSettings, AccessSettings and SecuritySettings, AccessSettings nested names, real tree clean, real tree coverage (>= 30 owners), Makefile and CI wiring.

Evidence (2026-10-20, from app/)
- uv run ruff check . : All checks passed!
- uv run ruff format --check on the two new files: clean after format
- uv run mypy bin/check_settings_key_ownership.py tests/unit/bin/test_bin_settings_key_ownership_check.py : Success: no issues found in 2 source files (0 errors in touched Python files)
- make check-settings-key-ownership : OK
- uv run pytest tests/integration/server/test_lifespan_vendor_slice_validation.py : 4 passed (AC2)
- uv run pytest tests --ignore=tests/smoke : 5435 passed

For the human
- CI picks up the new step on the PR; no deploy or environment change.
- Found outside scope: infrastructure/logging/setup.py _is_test_environment derives the environment from "pytest" in sys.modules, which configuration.md's environment identity rule prohibits; raised in session, no task created.
<!-- SECTION:NOTES:END -->
