---
id: TASK-24.1
title: >-
  Move the Trello, MaxMind, Notify, OpsGenie and Sentinel settings to
  integrations/<vendor>/settings.py
status: Done
assignee:
  - '@me'
created_date: '2026-10-19 17:18'
updated_date: '2026-10-20 21:43'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
parent_task_id: TASK-24
priority: medium
ordinal: 399000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-24 (decisions/configuration.md, Settings live with their owner). A pure move: each of the five vendors keeps one settings class, in integrations/<vendor>/settings.py next to its client, and its file under infrastructure/configuration/integrations/ is deleted. Env names, defaults and validation do not change; the environment renames ride with TASK-111.

The first commit amends decisions/configuration.md with the environment naming rule (<SLICE>__<FIELD>, decided 2026-10-19), so new and moved slices follow it from here.

Independent of Stack K: no open layer touches these files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Trello, MaxMind, Notify, OpsGenie and Sentinel each have exactly one settings class, in app/integrations/<vendor>/settings.py, and their files under app/infrastructure/configuration/integrations/ are deleted
- [x] #2 Env var names, defaults and validators are unchanged; existing settings tests pass against the new homes
- [x] #3 Every consumer and test imports from the new home; no re-export remains at the old path, and the matching import-linter ignore entries are deleted
- [x] #4 decisions/configuration.md records the environment naming rule and TASK-111 as the rename ticket
- [x] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Pure move, no behaviour change. Branch feat/task-24-vendor-settings from an up-to-date main (the TASK-24 planning edits ride on it as the first commit).

Commit 1 - planning: the TASK-24/24.x/111 task edits and the decisions/configuration.md amendment (environment naming rule <SLICE>__<FIELD>, TASK-111 renames, migration item, changes entry).

Commit 2 - the move.

Steps
1. Tests first (fail: the modules do not exist yet). New files under the layered tree, one per vendor:
   app/tests/unit/integrations/trello/test_trello_settings_load.py, .../maxmind/test_maxmind_settings_load.py, .../notify/test_notify_settings_load.py, .../opsgenie/test_opsgenie_settings_load.py, .../sentinel/test_sentinel_settings_load.py.
   Each: the getter returns one cached instance (cache_clear in a fixture); fields read their unchanged env names via monkeypatch.setenv; defaults hold when unset (MAXMIND_DB_PATH ./geodb/GeoLite2-City.mmdb, NOTIFY_API_URL "", SENTINEL_LOG_TYPE DevSREBot, the rest None); model_config is env_file .env, case_sensitive True, extra ignore. These replace TestMaxMind/Notify/OpsGenie/Sentinel/TrelloSettingsSingleton in tests/unit/infrastructure/configuration/test_integration_settings_singletons.py:83-160, which are deleted there (legacy file edited in place; Slack and Google stay).
2. Create app/integrations/{trello,maxmind,notify,opsgenie,sentinel}/settings.py, moving each class and its lru_cache getter verbatim from app/infrastructure/configuration/integrations/<vendor>.py, in the new-home convention (integrations/slack/settings.py, openai/settings.py): subclass pydantic_settings.BaseSettings with an explicit model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore"), identical to IntegrationSettings (infrastructure/configuration/base.py:6-17), so the vendor package stops importing infrastructure. The redundant alias equal to the field name is dropped (same env name under case_sensitive=True; the ADR rule bans per-field aliases). Class names (OpsGenieSettings casing included) and getter names unchanged.
3. Point the clients at the new home: integrations/trello/client.py:5, sentinel/client.py:12, notify/client.py:12, maxmind/client.py:12 and :15 (TYPE_CHECKING), opsgenie/client.py:7. Notify's get_app_settings import (:11) is out of scope.
4. Delete app/infrastructure/configuration/integrations/{trello,maxmind,notify,opsgenie,sentinel}.py and their import blocks and __all__ entries in that package's __init__.py (:9-24, :29-32, :38-50). Google and Slack stay until TASK-24.3/24.4.
5. pyproject.toml import-linter: delete the five now-unmatched ignore entries in both blocks (maxmind :248/:330, notify :250/:332, opsgenie :251/:333, sentinel :253/:335, trello :257/:339); unmatched_ignore_imports_alerting=error makes a leftover fail lint-imports.
6. Remaining tests: test_settings_structure.py:33-42 and :129-146 drop the five classes (they no longer subclass IntegrationSettings); test_settings_delegation.py:25-30, :43-47, :63-67 import the getters from the new homes, and its stale "Settings()" docstring (:1-5) is corrected; tests/unit/infrastructure/services/test_narrow_slice_providers.py:14 imports MaxMindSettings from integrations.maxmind.settings. tests/integrations/notify/test_notify_client.py:13 patches integrations.notify.client.get_notify_settings, which stays valid.
7. Docs: decisions/configuration.md:15 and decisions/outbound-clients.md:75 name only the vendors still in infrastructure/configuration/integrations/ (Google, Slack).
8. Gates from app/: ruff check ., mypy (0 new in touched files), lint-imports, pytest tests --ignore=tests/smoke.

AC traceability
- AC1 (one class, old files deleted) <- steps 2, 4; tests step 1, rg "configuration.integrations.(trello|maxmind|notify|opsgenie|sentinel)" returns nothing.
- AC2 (env names, defaults, validators unchanged) <- step 2; tests step 1 (env names and defaults asserted), existing client tests unchanged.
- AC3 (consumers on new home, no re-export, ignores deleted) <- steps 3, 4, 5, 6; lint-imports, rg.
- AC4 (ADR rule) <- commit 1.
- AC5 (gates) <- step 8.

Test matrix: happy (env set -> field), boundary (unset -> default / None), cache identity (singleton), config shape (model_config); failure: none, the classes have no validators. Authorization/idempotency: n/a.

Size: production ~5 created (~170 LOC moved), 5 deleted, 5 client import lines, 1 __init__, pyproject (~10 lines), 2 ADR lines; tests 5 new, 4 edited. About 28 files, all mechanical: over the ~10-file guideline, accepted as a pure move (human, 2026-10-19).

Assumptions and doubts
- Dropping alias=<same name> keeps the env name: verified by the step 1 env tests under case_sensitive=True.
- No consumer outside the survey: rg for each class and getter name before step 4.
- Module-level settings reads in the trello, sentinel, notify and opsgenie clients (import-time instantiation) stay as they are: changing them changes client construction, which is not a move. Raised as a question, not fixed here.

Blast radius and rollback: an import error in a client fails the module's import at boot or in a legacy command; covered by the client tests and the full pytest run. One git revert restores everything; no env, deploy or data change. No ordering constraint: no Stack K layer touches these files.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed (pure move, no behaviour change)
- New app/integrations/{trello,maxmind,notify,opsgenie,sentinel}/settings.py: the five classes and lru_cache getters moved unchanged in name, fields, defaults and env names. They subclass BaseSettings with an explicit model_config (env_file .env, case_sensitive, extra ignore), identical to IntegrationSettings, so the vendor packages no longer import infrastructure. The redundant alias equal to each field name is dropped (same env name under case_sensitive; the ADR rule bans per-field aliases).
- The five clients import from their own settings module. The five old files are deleted, and infrastructure/configuration/integrations/__init__.py exports only Google and Slack.
- pyproject.toml: the 10 now-unmatched import-linter ignores are deleted (5 per contract).
- Docs: decisions/configuration.md (current-state line) and decisions/outbound-clients.md (6 remaining integrations->infrastructure imports; only Google and Slack settings left in the old package). The naming rule itself landed in the planning commit.
- Tests: tests/unit/integrations/<vendor>/test_<vendor>_settings_load.py (26 tests: singleton, each field from its env var, defaults, model_config) replace the five vendor classes in test_integration_settings_singletons.py; test_settings_structure.py and test_narrow_slice_providers.py drop or repoint the five classes; stale PR-2/PR-6 docstring labels fixed.
- Deviation from plan step 6: tests/unit/infrastructure/configuration/test_settings_delegation.py is deleted, not edited. It defined no tests (an autouse cache-clearing fixture only) and its docstring described the removed Settings aggregator.

Evidence (from app/)
- uv run ruff check . -> All checks passed!; ruff format --check . -> 958 files already formatted
- uv run lint-imports -> Contracts: 12 kept, 0 broken
- uv run mypy . --exclude .venv -> Found 48 errors in 19 files; 0 in touched files (all in legacy modules/ and other untouched files)
- uv run pytest tests --ignore=tests/smoke -> 5055 passed
- rg for configuration.integrations.(trello|maxmind|notify|opsgenie|sentinel) outside backlog/ -> no hits

Open question for review: the trello, sentinel, notify and opsgenie clients read their settings at import time (module-level get_*_settings()); left as is because changing it changes client construction.

Human: review, commit, open the PR (reference decisions/configuration.md).
<!-- SECTION:NOTES:END -->
