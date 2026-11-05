---
id: TASK-145.5.7.3
title: incident.response becomes a plugin and registers the upgrade job
status: In Progress
assignee: []
created_date: '2026-11-04T14:04:00Z'
updated_date: '2026-11-04T23:10:00Z'
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
- [x] #1 incident.response is an entry point (pyproject.toml), protected by import-linter contract (m), enabled in base.toml, false in ci.toml, absent from production.toml, pinned in pytest-env; plugin enablement boot test and the ci requirements guard stay green
- [x] #2 [incident_response] upgrade_mode (off|dry_run|apply, default off), upgrade_interval_minutes (default 30) and upgrade_lease_ttl_seconds are declared in response/settings.py and base.toml; with mode off nothing is registered
- [x] #3 With dry_run or apply the plugin registers one interval job through BackgroundJobRegistry at lifespan startup (never at import) with lease_ttl from upgrade_lease_ttl_seconds, and register_requirements declares the Slack and Google tenants
- [x] #4 Each run opens one ServiceScopeOpener scope, resolves RecordStore, ConfiguredSystems and TenantVerifier, and runs the core runner with apply true only for mode apply; exceptions propagate to safe_run, which logs them once at error with the traceback (the job never logs and re-raises)
- [x] #5 features/incident/README.md records the run procedure (per environment, dry run then apply; after TASK-145.8 deploys and again after TASK-145.12; first production dry-run confirms the auth.test org-token shape; running it is a precondition of TASK-145.9) and TASK-145.13 as removal owner; the ADR lines written by the other session are present (checked, not authored)
- [x] #6 Verified by targeted tests, ruff, then once mypy and once full pytest, from app/; make check-import-contracts and make check-settings-key-ownership are green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
FULL PLAN (2026-11-04, against the stack: 11c branch on top of 11b #1821 and 11a #1820; main 4cbf7266). STATUS: awaiting human review. Replaces the outline; OQ11 (entry module features.incident.response.plugin) is applied throughout.

SIZE AND GATE: 9 production files (2 new) if OQ20 is approved as recommended (8 without it), ~137 production LOC + ~25 README lines; one behaviour subsystem (incident response plugin) plus its configuration (pyproject, base/ci TOML). No terraform, task definition, IAM, SSM or environment-name change (the three keys are files keys; their INCIDENT_RESPONSE__ overrides exist by construction, none is set anywhere). Gate passes.
DOMAIN MODEL: no entity is introduced or reshaped (settings keys, a settings enum and plugin wiring only; the record shape was decided in 145.5.7.2), so the domain-model-evolution gate is not applicable.

STEPS
1. app/pyproject.toml (+3 lines)
   - :44 entry point, beside incident.comms: "incident.response" = "features.incident.response.plugin".
   - :458 contract (m) protected_modules: add "features.incident.response.plugin" (the boot test at tests/integration/server/test_server_plugins_enablement_boot.py:96 keeps it equal to the entry points). No ignore_imports entry. response/settings.py and response/__init__.py stay importable by server/configuration/host_configuration.py:22,244 and modules/incident/{core,incident}.py.
   - :134 pytest-env pin PLUGINS__INCIDENT_RESPONSE gains "incident.response": false (the table is pinned whole, as ci sets it).
   - Contract (i) already layers response above core; unchanged.
2. app/features/incident/response/settings.py (+~25)
   - class UpgradeMode(StrEnum): OFF="off", DRY_RUN="dry_run", APPLY="apply".
   - upgrade_mode: UpgradeMode = OFF; upgrade_interval_minutes: int = Field(30, ge=1); upgrade_lease_ttl_seconds: int = Field(900, ge=1). Each with a Field description; class docstring Keys list extended; module docstring names the job keys and TASK-145.13 as their removal owner.
   - TTL 900 s (OQ17): 323 production items = one capped read plus at most 323 conditional updates, well under a minute; 15 min covers a slow run with margin and stays under the 30 min interval, so a replica that dies holding the lease never blocks the next run (reliability.md: TTL sized to the job's own max run).
3. app/config/base.toml (+~8): [incident_response] gains the three keys with a comment (mode off registers nothing; an environment switches it on in its own file for the run procedure); [plugins.incident_response] gains "incident.response" = true (D4).
   app/config/ci.toml (+1): [plugins.incident_response] "incident.response" = false (the ci requirements guard demands it, since the plugin states requirements). production.toml: no change (D4).
4. app/features/incident/response/plugin.py (new, ~40): module docstring (registration is startup-driven, hookimpls only, no import-time side effect; TASK-145.13 deletes the job hookimpl and keys).
   - @hookimpl register_requirements() -> (Requirement("slack.tenant"), Requirement("google_workspace.tenant")) (ids as in features/incident/scribe/__init__.py:22).
   - @hookimpl register_background_jobs(registry: BackgroundJobRegistry): settings = get_incident_response_settings(); mode OFF -> logger.debug("incident_legacy_upgrade_not_registered", reason="upgrade_mode_off") and return; else registry.register_interval(job_name="incident_legacy_upgrade", every=timedelta(minutes=settings.upgrade_interval_minutes), job=partial(run_legacy_upgrade, registry.service_scopes, apply=mode is APPLY), lease_ttl=timedelta(seconds=settings.upgrade_lease_ttl_seconds)). If partial lacks __module__/__name__ for safe_run's log (jobs/scheduled_tasks.py:97-99,111-112), use a named nested function instead (verify in the registration test).
   - response/__init__.py docstring (~3 lines): the subdomain now registers the upgrade job through plugin.py; settings.py stays importable by the host and the legacy modules.
5. app/features/incident/response/legacy_upgrade_job.py (new, ~45): run_legacy_upgrade(scopes: ServiceScopeOpener, *, apply: bool) -> None:
   with scopes.create_scope() as services: records = services.get(RecordStore); systems = services.get(ConfiguredSystems); verifier = services.get(TenantVerifier); build_legacy_upgrade(records, systems, verifier, get_incident_core_settings()).run(apply=apply).
   No try/except: an exception propagates to safe_run, which logs it once (OQ20); the scope and the lease are released on the way out (context manager; run_if_leased's finally). The runner already logs the one report event per run; the job adds nothing on success. Imports: contracts.records, contracts.workplace, contracts.services, features.incident.core.api, features.incident.common.settings (contracts (b), (e), (i) hold).
6. app/features/incident/README.md (+~25): response/ row (:23) becomes "settings.py plus plugin.py (entry point incident.response: register_requirements Slack and Google tenants; register_background_jobs registers the legacy upgrade job when upgrade_mode is not off) and legacy_upgrade_job.py (the job body)"; core row (:16) "not registered yet: response/ registers it in TASK-145.5.7.3" becomes "registered by response/". New "Legacy upgrade run procedure" section below the table:
   - Preconditions: the first run follows TASK-145.8's deploy (the upgrade writes status, severity, security_incident and the two roles in their end-state form, OQ13); [scheduler] enabled in that environment.
   - A dry run with blockers is a failed run logged at error (OQ15), so it trips the error alarm on every run: after reading the first blocked report, a PR sets the mode back to off while the items are fixed by hand.
   - Per environment, dry run first: a PR sets [incident_response] upgrade_mode = "dry_run" in that environment's file (production: production.toml through the deploy workflow, never a console change); after the deploy the first report arrives within upgrade_interval_minutes (the scheduler's first run is one interval after boot, OQ19); read incident_legacy_upgrade_report (pending, unmatched_status, unreadable, dropped, tenant_check with the received ids). The first production dry run confirms D10's auth.test org-token shape: tenant_check verified; a mismatch is fixed by configuration ([slack.tenant] enterprise_id), not code. Fix listed items by hand, then a PR sets "apply"; confirm a later report shows pending 0, then a PR sets "off" (OQ18).
   - Run again after TASK-145.12; running it is a precondition of TASK-145.9 merging; TASK-145.13 removes plugin.py's job hookimpl and the three keys once a production run reports nothing pending.
   - Local: INCIDENT_RESPONSE__UPGRADE_MODE=dry_run and SCHEDULER__ENABLED=true in app/.env; the plugin needs the Slack and Google tenants, as incident.scribe already does.
   ADR lines are checked present, not authored: decisions/incident-management.md:128 (tolerated response job), :158, :161; decisions/plugins.md:110 (submodule entry point); decisions/reliability.md:67 (lease_ttl).

AC -> STEP -> TEST (tests under app/tests/; unit unless noted)
AC1 -> steps 1, 3 -> tests/integration/server/test_server_plugins_enablement_boot.py (entry point = contract (m) list, one base key per entry point; :66 disabled set gains incident.response); test_server_plugins_ci_requirements_guard.py (:43 stating set gains incident.response; nothing stating is on in ci); test_lifespan_plugin_loading.py (:34 DISABLED_PLUGINS gains incident.response); test_server_lifespan_configuration_phase.py (:157 disabled set gains incident.response).
AC2 -> steps 2, 3 -> tests/unit/features/incident/response/test_incident_response_settings_load.py: test_base_declares_every_key_empty (:43) narrowed to the id keys plus a test that base declares the three upgrade keys at off/30/900; production.toml and ci.toml set no upgrade key; "nonsense" mode, interval 0 and ttl 0 each fail naming the key; tests/unit/features/incident/response/test_incident_response_upgrade_job_register.py: mode off registers nothing.
AC3 -> step 4 -> test_incident_response_upgrade_job_register.py with a recording BackgroundJobRegistry (local class over FakeServiceScopeOpener): dry_run and apply each register exactly one interval job "incident_legacy_upgrade" with every = interval minutes and lease_ttl = upgrade_lease_ttl_seconds; register_requirements returns the Slack and Google tenants; importing plugin.py registers nothing (a fresh import, the recording registry stays empty).
AC4 -> step 5 -> tests/unit/features/incident/response/test_incident_response_upgrade_job_run.py, over FakeServiceScopeOpener {RecordStore: records_with(legacy_item()), ConfiguredSystems: fake tenants, TenantVerifier: verified_slack()} from tests/factories/{services,legacy_upgrade}.py: one scope opened and closed per run; dry_run writes nothing; apply writes the item (update recorded); a missing service (KeyError) is logged as incident_legacy_upgrade_failed, re-raised, and the scope is still closed; the registered job (from AC3) run with mode apply passes apply=True.
AC5 -> step 6 -> review; grep for the ADR lines listed in step 6.
AC6 -> all -> ruff and the targeted files during TDD; make check-import-contracts, make check-settings-key-ownership; then mypy once and the full pytest once, sequentially.
Reverse trace: every new or changed test above maps to one AC; no step lacks a test except the README (AC5, review).

TEST MATRIX: happy (dry_run and apply register and run), boundary (mode off registers nothing; interval and ttl at 1 accepted, 0 rejected), failure (invalid mode; missing service re-raised with the scope closed), idempotency (apply then a second run: already_upgraded, no write; covered by 145.5.7.2's runner tests, not repeated), import side-effect free.

ASSUMPTIONS (each verified by a test named above)
- pm.load_setuptools_entrypoints loads a submodule entry point (plugins.md:110): the enablement boot test and the ci guard load it. The installed dist's entry points refresh on uv sync (the editable install); verify with the guard test after the pyproject edit.
- register_background_jobs fires only with [scheduler] enabled (server/lifespan.py:102-107): production true (config/production.toml:11), base false; so ci and local without SCHEDULER__ENABLED never register the job whatever the mode.
- Production has the Slack and Google tenants (incident.scribe requires both and is on today), so enabling incident.response in base never aborts the production boot (TASK-172).

BLAST RADIUS AND ROLLBACK: merging deploys a plugin that loads in production and registers nothing (mode off): one DEBUG line and the plugin in the startup summary. Wrong only if production lacked a tenant (boot aborts naming it; it has both). One git revert removes the plugin, keys and entry point. Ordering: none for the merge; the first dry run waits on TASK-145.8's deploy (README).

OPEN QUESTIONS, assessed at program scope (2026-11-04: ADRs, doc-11, doc-15, prior and upcoming tasks; recommendation first)
- OQ17 lease TTL 900 s, interval 30 min. ADR: covered, no gap. reliability.md (Background jobs): the TTL is the job's own setting, sized to its expected max run; takeover on over-run is acceptable because the body is idempotent; 2026-11-04 line names this job as the first lease_ttl user. Prior: D5 fixed the interval at 30 (approved); the scheduler's default_tier2_lease_ttl_seconds is 1800 (base.toml:181) for unmigrated jobs. Upcoming: 145.9 (nudge) and 147.6 (reminders) size theirs the same way. Sizing evidence: the incidents table is provisioned at 2 RCU / 2 WCU (terraform/dynamodb.tf:91-95); 323 items, so the read is ~40-80 RCU and the writes ~323-646 WCU. With DynamoDB's burst reserve (up to 300 s of unused capacity, best effort) a run takes seconds; with none it is about 3-6 min at 2 WCU/s. ShedLock's guidance is a lock-at-most much longer than the normal run, a fallback for a dead node only. 900 s is about 2.5x the no-burst worst case and stays under the 30 min interval, so a dead holder's lease always expires before the next tick. A run cut by throttling ends write_failed and the next run resumes (every write is guarded on record_version absent). Recommend 900 as written.
- OQ18 the job keeps running while the mode is dry_run or apply; the procedure ends with off. ADR: covered. incident-management.md Migration rule 6 (the backfill is final only once no legacy writer remains, so it is rerun after the last legacy writer is removed) and the parent plan (run after 145.8, again after 145.12) describe discrete runs; TASK-145.12 AC2 records the rerun; TASK-145.13 AC5 deletes the job after a production run reports nothing pending; 145.9's precondition is pending 0. Leaving apply on until 145.12 would also catch the sheet import's legacy items (a dev command, modules/dev/incident.py), but an item with a blocker then fails every 30 min at error. Recommend off after a clean apply, as written, with the blocked-dry-run line added to the README (above).
- OQ19 the first run is one interval after boot. ADR: gap, minor. reliability.md and the registry Protocol (contracts/scheduler/registry.py) say nothing about first-run timing; the schedule library runs an interval job one interval after registration, so every deploy restarts that clock. Other schedulers make it explicit: Spring @Scheduled(initialDelay), APScheduler next_run_time, Quartz startNow. Upcoming: TASK-64 widens the schedule expression (AC1). For this job a wait of up to 30 min is harmless (a migration read by a person from the report). Recommend: accept and state it in the README; add a note to TASK-64 that its schedule expression states the first run (after one interval, today's behaviour, or at registration) so the next job that needs it does not rely on the library default. No ADR change now; TASK-64 records it in reliability.md when it lands.
- OQ20 (replaces the logging question) a failed run is logged once, by safe_run, with the traceback; the job does not log and re-raise. ADR: gap. reliability.md says the host owns the safe_run error boundary; observability.md "Exceptions render once" puts the traceback inside the structured event; but safe_run (jobs/scheduled_tasks.py:103-117) logs safe_run_error with error=str(e) and no exc_info, so a job that only re-raises loses its traceback, and one that logs and re-raises emits two error events per failure (two alarm hits). Current practice is to log at the handler that ends the error, once, with the traceback, and have inner code add context and re-raise without logging (Sonar RSPEC-2139; "log or rethrow, not both"). Fix: safe_run logs with exc_info (logger.exception), one line plus a unit test (tests/unit/jobs/test_jobs_safe_run_log.py: the event carries the exception and its traceback once); the job keeps no try/except. Context: safe_run already names module and function; the mode is in the startup configuration_slice event. ADR: reliability.md Background jobs gains "the error boundary logs a failed run once at error with the traceback; a job body never logs and re-raises" with a Changes line; TASK-64 AC2 and TASK-52 AC1 carry the rule when they move safe_run (notes). AC4 reworded to: "exceptions propagate to safe_run, which logs them once at error with the traceback". Where: in 11c (adds jobs/scheduled_tasks.py: 9 production files, ~137 LOC, still under the gate; the host error boundary is the one extra subsystem). Alternative: on 11a's branch (#1820, still in review, already edits that file), at the cost of a re-review and a gh stack rebase. Recommend 11c.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved): OQ11: the plugin's entry module is features.incident.response.plugin (hookimpls in response/plugin.py); entry point "incident.response" = "features.incident.response.plugin" and contract (m) protects that module, so features.incident.response.settings stays importable by the host configuration phase and the legacy modules until TASK-145.13 (plugins.md: one entry point per plugin module).

2026-11-04 (human): plan approved with OQ17-OQ20 as recommended after the program-scope assessment (written into the plan): OQ17 lease 900 s, interval 30 min; OQ18 the procedure ends with mode off after a clean apply, and a blocked dry run is switched off while items are fixed; OQ19 the first run is one interval after boot, stated in the README, TASK-64 notes that its schedule expression states the first run; OQ20 safe_run logs a failed run once with the traceback (jobs/scheduled_tasks.py, in this layer), the job never logs and re-raises; AC4 reworded to match; reliability.md gains the rule; TASK-64 and TASK-52 carry it.

2026-11-04 implemented with TDD on stack-k/task-145.5.7.3-response-registers-upgrade (on 11b #1821), uncommitted. Production: pyproject.toml (entry point incident.response = features.incident.response.plugin, contract (m) entry, pytest-env pin false), response/settings.py (UpgradeMode off|dry_run|apply; upgrade_mode off, upgrade_interval_minutes 30 ge 1, upgrade_lease_ttl_seconds 900 ge 1), new response/plugin.py (register_requirements Slack + Google tenants; register_background_jobs: off registers nothing (DEBUG incident_legacy_upgrade_not_registered), else one interval job incident_legacy_upgrade with lease_ttl, a named closure so safe_run logs module and name), new response/legacy_upgrade_job.py (one scope, resolves RecordStore, ConfiguredSystems, TenantVerifier, build_legacy_upgrade(...).run(apply=...); no try/except), response/__init__.py docstring, base.toml (three keys, incident.response = true), ci.toml (incident.response = false), jobs/scheduled_tasks.py (safe_run logs exc_info, OQ20), README (rows and run procedure). 9 code/config files, ~85 LOC + 36 README lines; production.toml unchanged. ADR: reliability.md Background jobs (boundary logs once with traceback; first-run timing is the library default until TASK-64) + Changes line; plugins.md body sentence for the plugin submodule entry point (the 2026-11-04 Changes line already existed; the declaration test enforced the old rule, so the rule now sits in the body too). Present and checked: incident-management.md :128, :158, :161; plugins.md :110; reliability.md :67. Tests: settings load (+9 cases, base test narrowed), new upgrade_job_register (7) and upgrade_job_run (4), new jobs safe_run_log (2); entrypoint_declaration allows <package>.plugin targets; incident.response added to the disabled or requiring sets in enablement_boot, ci_requirements_guard, plugin_loading, configuration_phase, openai_requirement. Gates: ruff clean; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK; mypy 41 errors in 14 files, all pre-existing, none in touched files; pytest tests --ignore=tests/smoke 6249 passed.
<!-- SECTION:NOTES:END -->
