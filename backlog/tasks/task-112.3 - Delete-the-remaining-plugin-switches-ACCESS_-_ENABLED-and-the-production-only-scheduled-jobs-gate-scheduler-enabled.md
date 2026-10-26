---
id: TASK-112.3
title: >-
  Delete the access plugin switches ACCESS_*_ENABLED; each access plugin
  validates only its own settings
status: In Progress
assignee: []
created_date: '2026-10-23T19:21:00Z'
updated_date: '2026-10-26T17:11:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-112.2
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/reliability.md
parent_task_id: TASK-112
priority: medium
type: feature
ordinal: 441000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-112 (narrowed 2026-10-26, human: the scheduler half moved to TASK-112.4). The access plugins' in-code switches go: AccessSyncSettings.enabled (ACCESS_SYNC_ENABLED), AccessRequestsSettings.enabled (ACCESS_REQUESTS_ENABLED) and AccessCatalogSettings.enabled (ACCESS_CATALOG_ENABLED) and every 'if not settings.enabled' guard; the [plugins.platform_access] keys from TASK-112.2 decide instead (false in base and production, as today), and a disabled plugin is never imported (pm.set_blocked, protected-plugins import contract).

Each access plugin validates only its own settings (decisions/configuration.md: a setting a feature needs only when enabled is required by that feature's slice, validated only when the plugin is enabled; the requests fallback-slug validator is the pattern). Today one AccessSettings root builds sync, requests, catalog and config together, so once 'enabled' is gone the requests validator would fail a sync-only deployment. The root splits into per-plugin settings classes in common/settings.py (same env names), each built by its own plugin's provider; the requests one requires the fallback slug unconditionally. reconciliation_enabled is a job sub-switch and stays. Moving the access settings onto the configuration files is TASK-166's (production sets no ACCESS_* value, doc-14).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ACCESS_SYNC_ENABLED, ACCESS_REQUESTS_ENABLED and ACCESS_CATALOG_ENABLED are no longer read; a disabled access plugin has no routes and an enabled one works without them (tests)
- [x] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
- [x] #3 Access request fallback-approver slug is required exactly when the access.request plugin is enabled (a sync-only deployment boots without it), asserted by tests
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STATUS: split approved 2026-10-26 (human); slice A plan revised for the per-plugin settings (question 2), awaiting approval. Branch from main after TASK-112.2 (6c704dc1) merges.

CALL SITES (app/)
packages/access/common/settings.py: enabled fields :67 (sync), :88 (requests), :111 (catalog); fallback-slug model_validator :95-100 keyed on enabled; AccessSettings root :114-145 (env_prefix ACCESS_, nested delimiter _, max split 1, extra=ignore); get_access_settings :148-153; docstrings :8-10, :57, :80, :108, :121-124. Readers: request/providers.py:26 (.requests), sync/providers.py:22 (.sync), catalog/providers.py:26 (.catalog), common/providers.py:36 (.config). No plugin reads a sibling's sub-settings.
Guards and log fields: sync/__init__.py:70,74-79,98; request/__init__.py:54,59-64; catalog/__init__.py:29,32-37. Interaction guards and dataclass enabled fields: sync/interactions/ingress.py:38,72,155; sync/interactions/http.py:53,139; catalog/interactions/http.py:37,99,142; request/interactions/http.py:46,189,254,304,354,409,456; dead "not enabled" Slack text sync/interactions/slack.py:198,291. pyproject.toml:133 pytest-env ACCESS_SYNC_ENABLED=false (+ comment :129-132). READMEs: access/README.md:27,32,36; common/README.md:8-10,18-20,30-39; sync/README.md:91,100; request/README.md:78; catalog/README.md:69-74.
Tests touching enabled: tests/unit/packages/access/{common/test_settings.py, sync/test_config.py, sync/conftest.py, sync/test_access_sync_package_init.py, sync/test_access_sync_routes.py, sync/test_access_sync_ingress_lock_token.py, request/test_access_request_routes.py, request/test_access_request_package_init.py, catalog/test_access_catalog_routes.py, catalog/test_access_catalog_package_init.py}; tests/integration/packages/access/{request/test_routes.py, sync/conftest.py:78, test_access_plugin_discovery_registration.py}.
Config surfaces: terraform/, .github/workflows/, .devcontainer/, Dockerfile, Makefile: no ACCESS_*_ENABLED line. doc-14:23 production sets no ACCESS_* key.

SIZE: 9 production code files (8 access + pyproject), about -150/+50 LOC, 5 READMEs, about 14 test files. One subsystem (access package). Gate passes on code files; READMEs are documentation of the same change.

STEPS (TDD)
A1 tests first: access tests build routes and warmup without an enabled flag; failing tests: no settings class has an enabled field; ACCESS_SYNC_ENABLED, ACCESS_REQUESTS_ENABLED, ACCESS_CATALOG_ENABLED set in the environment change nothing; sync register_background_jobs registers iff reconciliation_enabled; per-plugin settings (A3).
A2 delete the switches: the three enabled fields; every 'if not settings.enabled' guard and the 503 / "not enabled" results; the interaction dataclasses' enabled field; the Slack "not enabled" branches (dead once a disabled plugin is never loaded); startup_warmup runs unconditionally (no early return, no access_*_disabled warning, no enabled= log field); pyproject pytest-env line and comment; five READMEs.
A3 per-plugin settings: in common/settings.py replace the AccessSettings root with four BaseSettings roots, AccessConfigSettings (ACCESS_CONFIG_), AccessSyncSettings (ACCESS_SYNC_), AccessRequestsSettings (ACCESS_REQUESTS_), AccessCatalogSettings (ACCESS_CATALOG_), each extra=ignore, case_sensitive=False, env_file=.env, with its own lru_cache getter (get_access_config_settings, get_access_sync_settings, get_access_requests_settings, get_access_catalog_settings). Same env names, so no production or .env change. AccessRequestsSettings requires fallback_approver_slug unconditionally (validator kept, enabled condition removed; message names ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG). The four providers switch to their getter; get_access_settings and AccessSettings are deleted (dead). The requests settings are built only by access.request's provider, which a disabled plugin never imports.
A4 one assertion in the 112.2 enablement boot test path: ACCESS_*_ENABLED=true with the plugin key false leaves the plugin unregistered.
New test files: tests/unit/packages/access/request/test_access_request_settings_fallback_slug.py (blank, whitespace, set; sync and catalog settings build without the slug); tests/unit/packages/access/common/test_access_settings_per_plugin_load.py (each getter reads only its prefix; env names unchanged; no enabled field).

AC TRACEABILITY: AC1 -> A1, A2, A4 -> access route, package-init and discovery tests. AC2 -> gates. AC3 -> A3 -> fallback-slug and per-plugin load tests.

TEST MATRIX: happy (enabled plugin serves without a flag; slug set), boundary (blank and whitespace slug; ACCESS_*_ENABLED set but ignored), failure (requests settings without the slug raise naming the key), isolation (sync-only settings load with no slug).

ASSUMPTIONS TO VERIFY: (1) production .env has no ACCESS_*_ENABLED line (doc-14; even if present, extra=ignore keeps boot safe; the post-plugins blob_where shows it). (2) sync/interactions/slack.py not-enabled branches follow only the ingress guard. (3) key-ownership check accepts four ACCESS_<SUB>_ prefixes without overlap (it compares full names case-folded).

BLAST RADIUS AND ROLLBACK: production unchanged (access plugins off by [plugins.platform_access]). Worst case a developer's ACCESS_*_ENABLED=true stops enabling a plugin locally. One git revert restores; no terraform or SSM change. Human: delete ACCESS_SYNC_ENABLED, ACCESS_REQUESTS_ENABLED, ACCESS_CATALOG_ENABLED lines from app/.env.example and personal .env/Codespaces secrets; the replacement is PLUGINS__PLATFORM_ACCESS='{"access.sync": true}'.

DEPLOY CHECK: phase post-plugins again (access absent from /sre help; /incident works), plus blob_where for the three ACCESS_*_ENABLED names.

2026-10-26 (human): plan approved.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-26 on task-112.3-access-switches (from main 5be2b74f after 112.2 merged as #1788).

Access switches: ACCESS_SYNC_ENABLED, ACCESS_REQUESTS_ENABLED and ACCESS_CATALOG_ENABLED are gone with every enabled guard, the 503 'not enabled' results, the ingress FEATURE_DISABLED path, the Slack 'not enabled' replies, the access_sync.disabled locale key and the disabled-warmup warnings. The AccessSettings root is split into AccessConfigSettings (ACCESS_CONFIG_), AccessSyncSettings (ACCESS_SYNC_) and AccessRequestsSettings (ACCESS_REQUESTS_), same env names, each built by its plugin's provider; the requests class requires ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG unconditionally. AccessCatalogSettings deleted (empty, dead); the single-JSON ACCESS_SYNC / ACCESS_REQUESTS form retired; the sync POST route documents 500 for an enqueue failure. The pytest-env guard moved to PLUGINS__PLATFORM_ACCESS all false. ADR: configuration.md Changes entry.

Dead code and docs riding along: six pytest-env names nothing reads (SRE_DRIVE_ID, SRE_INCIDENT_FOLDER, INCIDENT_TEMPLATE, INCIDENT_LIST, PICKLE_STRING, INCIDENT_HANDBOOK_URL; values come from GOOGLE_RESOURCES); doc-14's NOTIFY_OPS_CHANNEL_ID and NOTIFY_ONCALL_GROUP_ID rows corrected to [notify_api_key_leak]; the human removed the ACCESS_*_ENABLED lines from app/.env.example.

Helper scripts versioned (human decision: helpers, not app code; outputs in gitignored tmp/): bin/deploy-checks.zsh pre | post [CHECK ...] (one post phase plus named task checks, deleted once their task is Done; plugins remains for 112.2 and 112.3) and bin/env-checks.zsh (make env-checks) with app/bin/audit_env_names.py, one action per env name (none, delete, rename, check) across app/.env*, Codespaces, Actions, Dependabot and SSM, judged against the settings classes, workflow references, developer setup references, the names retired since TASK-111.1 and doc-14. Its migration part is deleted in TASK-111.15.2 (AC added). Runbook roll-back-a-deployment.md points to both deploy-checks phases.

Production checks 2026-10-26: merge gate met (pre 16:08Z: rollback tag 5be2b74f4e925781d831bf1d9a3942a7b3d596c6-2026-10-26; post-plugins 16:06Z shows no ACCESS_*_ENABLED in either blob). Env audit 16:20Z: blobs need no hand edit (retired lines inert until the blobs are deleted after 111.15.2); all eleven /sre-bot/* secrets set; repo Codespaces cleanup done by the human (GEO_DB_BUCKET restored as sre-bot-bucket: make dev-setup reads it).

Follow-up for the next task touching .devcontainer: docker-compose.yml expands MAXMIND_KEY into a LICENSE_KEY build arg the Dockerfile never declares (dead).

Gates (from app/, final tree): ruff check . passed; mypy 47 errors in 18 files = baseline, none in touched files (427 checked); pytest tests --ignore=tests/smoke 5751 passed; make check-import-contracts 13 kept; make check-settings-key-ownership OK.

Human: after deploy run zsh bin/deploy-checks.zsh post plugins; set Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T14:55:00Z

---

Planning: gate trips on file count (about 15 production code files, 5 READMEs, two subsystems). Proposed split for approval: 112.3 narrows to Slice A (delete ACCESS_*_ENABLED, ACs 1, 6, 5) and a sibling 112.4 takes Slice B ([scheduler], lifespan gate, guard, ACs 2, 3, 4, 7, 5; depends on 112.3). No AC removals proposed. AC #4 half is already done: decisions/reliability.md lines 34 and 60 record [scheduler] enabled.

---

created: 2026-10-26T15:05:00Z

---

2026-10-26 (human): split approved. Slice B ([scheduler] enabled, lifespan gate, guard) moved to TASK-112.4 with former ACs 2, 3, 4 and 7 (7 reworded: the scheduler starts independent of the Slack app). Question 2 reassessed against decisions/configuration.md:61: the slug stays a settings validator, on a requests-only settings class, instead of a startup_warmup check.

---
<!-- COMMENTS:END -->
