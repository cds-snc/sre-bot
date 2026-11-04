---
id: TASK-145.5.7.3
title: incident.response becomes a plugin and registers the upgrade job
status: To Do
assignee: []
created_date: '2026-11-04T14:04:00Z'
updated_date: '2026-11-04T14:18:00Z'
labels:
  - incident
  - features
  - reliability
dependencies:
  - TASK-145.5.7.2
references:
  - decisions/plugins.md
  - decisions/incident-management.md
  - decisions/configuration.md
parent_task_id: TASK-145.5.7
priority: medium
ordinal: 475000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of 3 of TASK-145.5.7 (Stack K layer on top of 145.5.7.2; branch stack-k/task-145.5.7.3-response-registers-upgrade). Plugin wiring, settings, configuration and run procedure. Ships with upgrade_mode off, so merging registers nothing.

D3: the job is registered by incident.response, made a plugin now: entry point in app/pyproject.toml beside incident.comms; entry in import-linter contract (m); one hookimpl module registering the job (register_background_jobs) and register_requirements for the Slack and Google tenants; pytest-env pin PLUGINS__INCIDENT_RESPONSE. No upgrade/ subdomain. TASK-145.13 deletes only the hookimpl lines and the job keys.
D4: "incident.response" = true in base.toml [plugins.incident_response]; false in ci.toml (the ci requirements guard test demands it); no key in production.toml. The mode is the only operational switch.
D5: keys in [incident_response] (response/settings.py): upgrade_mode (off|dry_run|apply, default off; off = not registered), upgrade_interval_minutes (default 30), upgrade_lease_ttl_seconds (sized to the job's max run), passed to register_interval(lease_ttl=...).
Run procedure goes in features/incident/README.md. The ADR lines are written by the other session; this slice only checks them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 incident.response is an entry point (pyproject.toml), protected by import-linter contract (m), enabled in base.toml, false in ci.toml, absent from production.toml, pinned in pytest-env; plugin enablement boot test and the ci requirements guard stay green
- [ ] #2 [incident_response] upgrade_mode (off|dry_run|apply, default off), upgrade_interval_minutes (default 30) and upgrade_lease_ttl_seconds are declared in response/settings.py and base.toml; with mode off nothing is registered
- [ ] #3 With dry_run or apply the plugin registers one interval job through BackgroundJobRegistry at lifespan startup (never at import) with lease_ttl from upgrade_lease_ttl_seconds, and register_requirements declares the Slack and Google tenants
- [ ] #4 Each run opens one ServiceScopeOpener scope, resolves RecordStore, ConfiguredSystems and TenantVerifier, and runs the core runner with apply true only for mode apply; exceptions are logged and re-raised to safe_run
- [ ] #5 features/incident/README.md records the run procedure (per environment, dry run then apply; after TASK-145.8 deploys and again after TASK-145.12; first production dry-run confirms the auth.test org-token shape; running it is a precondition of TASK-145.9) and TASK-145.13 as removal owner; the ADR lines written by the other session are present (checked, not authored)
- [ ] #6 Verified by targeted tests, ruff, then once mypy and once full pytest, from app/; make check-import-contracts and make check-settings-key-ownership are green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN OUTLINE (2026-11-04; full step-level plan refreshed at pickup). STATUS: awaiting human review.
SIZE: ~140 production LOC (+~25 README lines), 8 files, two small subsystems (incident response plugin, configuration/pyproject). Passes the gate (config files are cheap to review). Revert is safe: ships with upgrade_mode off, nothing registered.
DEPENDS ON 145.5.7.2.

CONFLICT 1 TO RESOLVE BEFORE PICKUP (human): D3 says one hookimpl in features/incident/response/__init__.py and a contract (m) entry for features.incident.response. Contract (m) (pyproject.toml:440-468) has allowed_importers = [] and a shrink-only ignore_imports ("never add one"), and three modules import features.incident.response.settings today: app/server/configuration/host_configuration.py:22 (called at :244), app/modules/incident/core.py:13, app/modules/incident/incident.py:11. Protecting the whole package would fail the contract on all three, and it would defeat "a disabled plugin is never imported". Proposed resolution (smallest deviation): entry point "incident.response" = "features.incident.response.plugin" and contract (m) lists features.incident.response.plugin; the hookimpls live in response/plugin.py, the job body in response/legacy_upgrade_job.py (imported only by plugin.py); response/__init__.py and response/settings.py stay importable by the host and legacy modules. Alternative: move IncidentResponseSettings out of the package (churns TASK-145.7 and settings ownership). TASK-145.13 deletes plugin.py hookimpl lines and job keys only, as D3 says.

FILES
1. app/pyproject.toml (+~4): entry point "incident.response" = "features.incident.response.plugin" beside incident.comms (:44); contract (m) protected list (:458 area); pytest-env PLUGINS__INCIDENT_RESPONSE pin (:134) gains "incident.response": false. Contract (i) (:393) already lists response; unchanged.
2. app/features/incident/response/settings.py (+~25): UpgradeMode StrEnum off|dry_run|apply; upgrade_mode (default off), upgrade_interval_minutes (default 30, ge=1), upgrade_lease_ttl_seconds (ge=1, default sized to the max run; 323 items today, so a few minutes of margin: pick at pickup and record why); docstring Keys list. app/config/base.toml [incident_response] the three keys with comments; [plugins.incident_response] "incident.response" = true (D4); app/config/ci.toml [plugins.incident_response] "incident.response" = false (guard demands it since the plugin states a requirement); production.toml: no key. check-settings-key-ownership stays green (keys inside the existing table).
3. app/features/incident/response/plugin.py (new, ~35): @hookimpl register_requirements -> [Requirement("slack.tenant"), Requirement("google_workspace.tenant")] (verify exact Requirement ids in server/plugins/requirements.py and the sibling incident.comms usage at pickup); @hookimpl register_background_jobs(registry): mode off -> one DEBUG skip event, register nothing; else registry.register_interval(job_name="incident_legacy_upgrade", every=timedelta(minutes=interval), job=<closure over registry.service_scopes and mode>, lease_ttl=timedelta(seconds=upgrade_lease_ttl_seconds)). No import-time side effects.
4. app/features/incident/response/legacy_upgrade_job.py (new, ~45): run(service_scopes, apply): with service_scopes.create_scope() as services: RecordStore, ConfiguredSystems, TenantVerifier from services.get(...), build_legacy_upgrade(...).run(apply=...); log and re-raise exceptions to safe_run. Report is logged by the runner.
5. app/features/incident/README.md (+~25 lines): run procedure per environment (set upgrade_mode = "dry_run" in the environment file or env override, deploy, read incident_legacy_upgrade_report incl. tenant_check received ids (first production dry run confirms the D10 org-token assumption), fix listed items by hand, then apply, confirm pending 0; rerun after TASK-145.8 deploys and again after TASK-145.12; running it is a precondition of TASK-145.9; TASK-145.13 removes the hookimpl lines and job keys once a production run reports nothing pending); new sentence below the core table, not inside it. ADR lines are written by the other session now: this slice only checks they are present (decisions/incident-management.md Changes/Checks, decisions/plugins.md entry list if any).

AC -> TEST (under app/tests/unit/features/incident/response/ unless noted)
AC1: tests/unit/server/plugins/test_server_plugins_enablement_check.py and tests/integration/server/test_server_plugins_ci_requirements_guard.py stay green; test_incident_response_plugin_entry_point.py (entry point resolves to the plugin module; equals the contract (m) list - existing boot test keeps the lists equal); test_server_plugins_settings_load.py extended for the new key.
AC2: tests/unit/features/incident/response/test_incident_response_settings_load.py extended (defaults, base.toml carries keys, invalid mode, 0 interval, 0 ttl rejected); test_incident_response_plugin_registration.py (mode off registers nothing).
AC3: test_incident_response_plugin_registration.py (dry_run and apply register one interval job with lease_ttl equal to the setting; requirements declared; importing the module registers nothing), using the recording registry fake in tests/factories.
AC4: test_incident_response_legacy_upgrade_job_scope.py (one scope opened and closed per run; apply flag only for mode apply; exception re-raised).
AC5: documentation review plus a README presence check by the human; ADR lines verified present by grep at review.
AC6: gates.

ASSUMPTIONS: pluggy loads a submodule entry point via pm.load_setuptools_entrypoints (decisions/plugins.md): verify with the boot test; production.toml has no [plugins.incident_response] table today (config/production.toml:25 is [incident_response] only), so an absent key falls back to base (true) and the plugin is on in production with mode off: verify with tests/unit/server/configuration/test_server_configuration_files_load.py.
BLAST/ROLLBACK: enabling the plugin in base.toml loads it everywhere except ci; it requires Slack and Google tenants, so a deployment without them fails boot naming the setting (decisions/plugins.md). Production has both; local dev needs them or an override (document in README). Revert removes the plugin and keys.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved): OQ11: the plugin's entry module is features.incident.response.plugin (hookimpls in response/plugin.py); entry point "incident.response" = "features.incident.response.plugin" and contract (m) protects that module, so features.incident.response.settings stays importable by the host configuration phase and the legacy modules until TASK-145.13 (plugins.md: one entry point per plugin module).
<!-- SECTION:NOTES:END -->
