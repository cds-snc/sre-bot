---
id: TASK-110.2
title: >-
  Load plugins from pyproject entry points and make any plugin load failure
  abort boot
status: In Progress
assignee: []
created_date: '2026-10-06 14:15'
updated_date: '2026-10-06 16:37'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-110.1
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
  - decisions/toolchain.md
parent_task_id: TASK-110
priority: high
type: feature
ordinal: 317000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The behaviour change of TASK-110, after TASK-110.1 leaves no modules/ hookimpl. Declare one entry point per plugin module under the PLUGIN_NAMESPACE group, replace the pkgutil walk with pm.load_setuptools_entrypoints, make import failures fatal, add the CI declaration check, and drop the walk tolerance from decisions/plugins.md and decisions/lifecycle.md. Standalone PR, deployed and observed on its own (doc-2). Scope and context: the TASK-110 description.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 pyproject.toml declares an entry point for every current plugin, with dotted <feature>.<subdomain> names for umbrella subdomains; umbrella packages have none
- [x] #2 Lifespan registers plugins only through pm.load_setuptools_entrypoints; no pkgutil/walk_packages discovery remains, and pm.register() for a first-party plugin appears only in test fixtures
- [x] #3 Boot tests: a poisoned entry point aborts boot; a raising hookimpl aborts boot; every expected plugin is registered
- [x] #4 CI check: every package shipping hookimpls has a matching entry-point line
- [x] #5 decisions/plugins.md and decisions/lifecycle.md drop the filesystem-walk tolerance in the same PR
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #7 The slack_provider_start_skipped log fires only in the test environment
- [x] #8 A one-off docker build --target builder check of the installed entry-point metadata and load_plugins is recorded in the task notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Depends on TASK-110.1 (no modules.* hookimpls remain, so no legacy plugin list is needed). Standalone deploy and observation per doc-2. Verified against main d3418396.

## Findings (path:line)
- Walk: app/server/plugins/base.py:13-58; logs and skips at :52-58. Only production caller: server/lifespan.py:187 inside `_initialize_translation_service` (:160-210), which then fires `register_i18n_resources` (:191). Slack/event/routes/warmup hooks: `register_feature_integrations` (manager.py:70). No try/except around hook calls: a raising hookimpl already aborts boot; only the import-skip is tolerated.
- Dead: manager.py:45 `collect_feature_i18n_resources`, :114 `discover_and_init_features`. app/bin/check_aws_platform_seam.py:33 comment names `auto_discover_plugins`.
- pyproject.toml: no entry points; hatchling; wheel packages list (:199). Editable dist in .venv has no entry_points.txt, so `uv sync` is required after the edit. Dockerfile builder already `uv sync --locked --no-dev --no-editable` (TASK-14).
- pluggy 1.6 `load_setuptools_entrypoints(group)` (.venv pluggy/_manager.py:392): import errors propagate; registers name=ep.name; skips already registered names (idempotent).
- Group name = `PLUGIN_NAMESPACE` = `sre_bot` (contracts/plugins/namespace.py:12).
- Plugins with hookimpls (eight, after 110.1): access.catalog (routes, warmup), access.request (routes, warmup), access.sync (slack, warmup, routes, jobs, i18n), geolocate (slack, routes, i18n), incident.scribe (slack, i18n), oncall_sync (jobs, warmup), rant (slack), user_rotations (slack). No entry point: access/common, incident umbrella, incident/core, scheduling (empty `__init__`), documents, drive, meet, aws_platform, talent, modules.*.
- Docs text to drop (AC#5): decisions/plugins.md:15, :87-88, check line :74 stays literal; decisions/lifecycle.md:17, :75-76.
- Misplaced log: server/lifespan.py:~304-311: `else: logger.info("slack_provider_start_skipped", reason="test_environment")` is attached to `if not start_slack_result.is_success`, so it logs on success and never in test env.

## Decisions
1. `load_plugins(pm, logger) -> None` in server/plugins/manager.py: `pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)`; if no plugin from the group is registered afterwards raise `RuntimeError("no_plugins_loaded: ... run uv sync")`; log `feature_plugins_loaded` with sorted names. No try/except; import errors and hookimpl exceptions abort the lifespan before yield. No `pm.register` anywhere in app code (AC#2 literal).
2. Delete base.py, `collect_feature_i18n_resources`, `discover_and_init_features`. Lifespan gets a `plugin_loading` phase before `_initialize_translation_service`, which keeps only the i18n hook and translator init; fix its empty docstring and shadowed `log`.
3. Eight entry points under `[project.entry-points.sre_bot]`, alphabetical, targets `packages.*`.
4. Lifespan fix: the skipped log moves under the outer `if not _is_test_environment():` as an `else:`.
5. CI declaration check is a pytest test (AST scan, no imports).
6. Poison/raising fixtures use a throwaway dist-info on sys.path (`monkeypatch.syspath_prepend`); no first-party mutation.
7. Image check (task notes, no workflow change): `docker build --target builder -t sre-bot:task110 -f Dockerfile .` from repo root, then in the image print `PLUGIN_NAMESPACE`, the group's entry points and run `load_plugins` on a bare pm; also `uv run --no-project python -c "import contracts.plugins.namespace"` shows `PackageNotFoundError`.

## Files (production) rough LOC
pyproject.toml +10; server/plugins/manager.py about -35 net; server/plugins/base.py deleted -50; server/lifespan.py about 30 changed; bin/check_aws_platform_seam.py comment 1; decisions/plugins.md and lifecycle.md about 15 (non-code). About 110 changed + 50 deleted, 5 code files + 2 docs, 1 subsystem.

## TDD test matrix (red first)
| File | Cases |
|---|---|
| tests/unit/server/plugins/test_server_plugins_loader_entrypoints.py (new) | loads fake-dist entry point under the name; zero plugins raises `no_plugins_loaded`; poisoned entry point (ImportError) propagates; second call idempotent |
| tests/unit/server/plugins/test_server_plugins_entrypoint_declaration.py (new) | AC#4 AST scan of packages/ both directions; hookimpls only in package `__init__`; names dotted for subdomains; umbrella/core/common/aws_platform absent; group == PLUGIN_NAMESPACE; installed metadata == pyproject; grep test: no `pkgutil`/`walk_packages` and no `pm.register(`/`.register(module` in non-test app code |
| tests/integration/server/test_lifespan_plugin_loading.py (new) | AC#3: lifespan with a poisoned entry point aborts before yield; raising hookimpl (fake dist) aborts; registered plugin-name set equals the eight pyproject entry points exactly (boot comparison) |
| tests/integration/server/test_lifespan_slack_start_log.py (new) | start success logs neither failure nor skipped; test env logs `slack_provider_start_skipped`; failure logs `slack_provider_start_failed` |
| edit in place: tests/integration/infrastructure/hooks/test_i18n_hook_discovery.py, tests/integration/packages/access/test_access_plugin_discovery_registration.py | switch `auto_discover_plugins` to `load_plugins`; same assertions |

## Steps
1. Red tests. 2. pyproject entry points; `uv sync`. 3. manager.py add `load_plugins`, delete dead functions. 4. Delete base.py. 5. lifespan phase, docstring/log fixes. 6. Update two integration tests, bin comment. 7. Docs. 8. Gates and image check, notes.

## Verification
cd app && uv sync && uv run ruff check . && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run lint-imports && uv run pytest tests --ignore=tests/smoke; docker build --target builder -t sre-bot:task110 -f ../Dockerfile .. then docker run metadata/load check.

## Assumptions and risks
- hatch writes entry_points.txt on `uv sync`; verify. Entry-point order follows declaration (tests must not depend on it; alphabetical keeps today's order).
- Missing/typo'd entry-point line silently drops a feature: declaration test plus boot-set equality test.
- A stale venv now aborts boot/tests loudly (intended; message says uv sync).
- Rollback: single revert (dev venvs need `uv sync`); no manifest ordering constraints. Out of scope: TASK-112 enablement, TASK-126 settings-skip/credential checks, features/ moves.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 implementation (verified against main 0c0add62).

Plan findings re-verified: same eight hookimpl packages, no modules/ hookimpl, dead manager functions present; the walk call had moved to lifespan.py:196. `uv sync` writes entry_points.txt for the editable install (hatch); uv.lock unchanged.

Deviation from the plan: tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py::test_incident_scheduling_has_no_entry_point forbade any packages.incident.* target and failed once incident.scribe was declared. Narrowed it to the umbrella and the scheduling package (its intent); its task-id docstring was rewritten. bin/check_aws_platform_seam.py's blind-spot note now says the walk is gone (seam check still OK, 11 baselined).

Gates (from app/):
- ruff check . -> All checks passed!
- mypy . --exclude venv -> Found 57 errors in 20 files (checked 369 source files); 0 in touched files.
- lint-imports -> Contracts: 9 kept, 0 broken.
- pytest tests --ignore=tests/smoke -> 6 failed, 3715 passed. The 6 are the known TASK-90 order leaks (3 in tests/modules/webhooks/test_webhooks_aws_sns.py, 3 in tests/unit/infrastructure/directory/test_google.py); both files pass alone (111 passed).

Image check (AC#8), from repo root: `docker build --target builder -t sre-bot:task110 -f Dockerfile .` built. In the image with /app/.venv/bin/python: PLUGIN_NAMESPACE = sre_bot; dist /app/.venv/lib/python3.14/site-packages/sre_bot-0.1.0.dist-info lists the eight [sre_bot] entry points; load_plugins on a bare pm logged feature_plugins_loaded with the eight names and registered exactly those. Bare-source check: `uv run --no-project` inside /app still resolves /app/.venv (sys.prefix /app/.venv, import succeeds), so it does not demonstrate the failure there; with the sre_bot dist-info moved out of site-packages, `import contracts.plugins.namespace` raises `PackageNotFoundError: No package metadata was found for sre-bot`, as intended.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-06 14:15
---
Plan approved by the human on 2026-10-06 (TASK-110 planning session): the TASK-110.1 / TASK-110.2 split; sre/dev go to the end state (no hookimpls, explicit legacy registration, AC#2 of 110.2 kept literally); top-level imports in lifespan.py matching the existing legacy list, no lazy import; the start-log fix in 110.2; the zero-plugins check in load_plugins; a one-off image build check, no CI workflow change.
---
<!-- COMMENTS:END -->
