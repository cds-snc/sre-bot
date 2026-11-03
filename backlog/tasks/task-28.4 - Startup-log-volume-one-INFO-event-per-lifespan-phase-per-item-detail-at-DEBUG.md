---
id: TASK-28.4
title: >-
  Startup log volume: one INFO event per lifespan phase, per-item detail at
  DEBUG
status: To Do
assignee: []
created_date: '2026-10-29T16:25:00Z'
updated_date: '2026-11-03T17:20:00Z'
labels:
  - observability
  - lifecycle
dependencies:
  - TASK-156
  - TASK-28.2
parent_task_id: TASK-28
priority: medium
ordinal: 461000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A boot writes many INFO lines that describe configuration and registration one step or one item at a time:
- configured_systems_built, initialized_audit_trail_service and initialized_record_store;
- feature_plugins_loaded, slack_commands_registered, event_handlers_registered, feature_routes_registered and feature_startup_warmup_completed;
- registering_legacy_handlers and legacy_slack_commands_registered;
- one line per webhook pattern at import (modules/webhooks: registered_pattern, pattern_registration_success);
- the i18n and security phase lines;
- slack_sdk's own startup lines.

TASK-156 makes configuration_summary and plugin_configuration_summary the record of what configuration a boot used, so the per-step configuration lines carry nothing those two events lack.

decisions/lifecycle.md says each phase is logged with its name, and observability.md says INFO means a state change. No ADR says how many INFO events a boot should emit, or which detail belongs at DEBUG. That is a gap: research current practice (OpenTelemetry, OWASP Logging Cheat Sheet, Spring Boot and ASP.NET Core startup logging) and record the rule in observability.md before changing levels.

Stage:
- Starts after TASK-156 is deployed and its post-deploy summary check passes, so nothing is dropped before its replacement is verified in production.
- Starts with or after TASK-28.2, which routes uvicorn and pre-configuration lines through the pipeline, so foreign startup lines get levels this task can set.
- Webhook pattern registration at import is TASK-168's (webhook pattern discovery), so this task only lowers those lines' level.
- Alarms and deploy checks that match a startup event must keep working: bin/deploy-checks.zsh pre/post, the CloudWatch filters in terraform, and TASK-94.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An inventory of every event one local boot and one production boot write before the first request, with each event's level and count, recorded in the task notes (production from zsh bin/deploy-checks.zsh output or a Logs Insights query the human runs)
- [ ] #2 observability.md records the startup logging rule (one INFO event per lifespan phase naming the phase, with counts; per-item registration and construction detail at DEBUG; configuration only in the generated summaries), with cited sources
- [ ] #3 Each lifespan phase emits one INFO event with its name and counts; per-item registration, construction and webhook-pattern lines log at DEBUG; no WARNING, ERROR or CRITICAL event changes level
- [ ] #4 No deploy check, alarm filter or test matches a removed or demoted event, verified by rg over bin/, terraform/, .github/ and app/tests
- [ ] #5 A boot test asserts the INFO event count of a ci boot stays at or below the agreed bound
- [ ] #6 ruff, lint-imports, mypy and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-03 (human): OQ1-OQ9 as recommended, OQ8 folded in (step 7a). Planned against task-28.2-uvicorn-logging; TASK-28.2 merged 2026-11-03 (#1814, 90ed5968) and deployed. Branch from main 90ed5968.

## Summary
Every lifespan phase logs exactly one INFO event that names the phase and carries counts. Per-item registration and construction lines drop to DEBUG. Configuration stays only in the generated configuration_slice / configuration_summary / plugin_configuration_summary events (configuration.md). WARNING/ERROR/CRITICAL events are untouched. uvicorn's four startup lines, slack_sdk's lines and TASK-168's import-time webhook discovery are not changed.

## Measured baseline (ci boot, outside pytest, structlog console render; see notes for the table)
78 INFO records before the first request: 28 configuration_slice/summary + 50 others, of which 31 are per-item (8 loaded_translations, 4 initialized_yaml_loader, 3 core_service_resolved, 2 i18n_resource_registered, 4 botocore, ...). Plus 13 plain webhook lines printed at import before logging is configured.

## Steps (each step names its AC)
0. ADR first (AC #2). Edit decisions/observability.md in the working tree before any code: add the "Startup logging rule" paragraph (text in the notes) and a Changes entry; lifecycle.md gets one sentence under the phase list pointing to it (phase event names) plus a Changes entry. Sources cited inside the text.
1. Tests first (AC #3, #5, #6): see Test matrix.
2. server/lifespan.py (AC #3)
   - security: log DEBUG security_services_initialization_started; the single INFO is security_services_initialized with issuer_count (also issuer_count=0 when no issuer is configured; the weakened-setting WARNING already says why).
   - directory: replace directory_provider_initialization_started / warmup_skipped / completed with DEBUG started and one INFO directory_provider_initialized(warmup=bool).
   - i18n: i18n_resources_collected and i18n_initialization_completed_and_healthy become one INFO i18n_initialized(resource_count, locale_count); the collected line goes DEBUG.
   - registering_legacy_handlers and legacy_slack_commands_registered go DEBUG; the registration phase INFO is feature_integrations_registered, whose counts now come from step 3. scheduled_tasks_started gains jobs=<count of scheduled jobs>. Others unchanged: application_startup, plugin_configuration_summary, scheduled_tasks_skipped, application_shutdown.
3. server/plugins/manager.py: plugin_manager_created, plugin_requirements_resolved, slack_commands_registered, event_handlers_registered, feature_routes_registered, feature_startup_warmup_completed go DEBUG. register_feature_integrations logs the one INFO feature_integrations_registered with counts (plugins that implemented register_slack_commands / register_routes / startup_warmup, from the per-plugin result dicts call_hook_per_plugin already returns); the lifespan's duplicate of that event is deleted. feature_plugins_loaded stays INFO unchanged (its tests assert its exact fields).
4. server/services.py: core_service_resolved and configured_systems_built go DEBUG; core_services_initialized(count) is the phase event.
5. bin/deploy-checks.zsh (AC #4): key boot detection on core_services_initialized instead of configured_systems_built (lines 95, 113, 158). The event exists in the running revision too, so pre and post work across the deploy. The tenant sample on line 158 is dropped (the configuration_slice events carry the tenant slices). Nothing else in bin/, terraform/, .github/ matches a demoted event. slack_app_initialized (lines 92, 156) stays INFO, and the slack_sdk "session has been established" / "on_error invoked" matches (lines 127, 157) stay valid because slack_sdk lines are not touched.
6. Per-item DEBUG demotions, one-line level swaps (AC #3):
   - infrastructure/records/service.py:185 initialized_record_store; infrastructure/audit/service.py:78 initialized_audit_trail_service
   - infrastructure/i18n: loader.py:80,125 (initialized_yaml_loader, loaded_translations), translator.py:44,49,61 (initialized_translator, loaded_all_translations, loaded_locale_translations), factory.py:73,76, resources.py:47,99, service.py:80,125 and healthcheck_passed
   - infrastructure/security/jwks.py:82,117,130; infrastructure/directory/google.py:398,405
   - integrations/slack/provider.py: slack_provider_initialized (247), initializing_slack_app (284), socket_mode_handler_prepared / disabled_http_mode (328,330), auto_registered_root_command (612, per root command), slack_interaction_listeners_attached (662) go DEBUG; slack_app_initialized (332) stays INFO and gains commands=<registered count>; socket_mode_started stays INFO
   - jobs/scheduled_tasks.py: initializing_scheduled_tasks (107), feature_background_job_scheduled (47,63, per job), scheduled_job_skipped (121)
   - packages: oncall_sync/__init__.py:61 oncall_sync_settings_loaded, access/sync (67,75), access/request (53,62), access/catalog:26 go DEBUG (settings are configuration, in the summaries only)
   - modules/webhooks: simple_text.py:229 registered_pattern, aws_sns_notification.py:336 registered_notification_pattern and :351 no_handlers_found_in_module go DEBUG; notification_handlers_initialization_complete (:414) stays INFO as that module's one summary. Delete modules/webhooks/patterns/examples.py whole: nothing imports it (rg), so pattern_registration_success is dead code with no caller.
7. infrastructure/logging/setup.py (after 28.2): one constant lowering the botocore logger to WARNING (see OQ5): it writes 4 INFO lines per boot in ci and one pair per client in production; DEBUG still shows them.
7a. Slack start on a Slack-off boot (OQ8, approved fold-in; server/lifespan.py and integrations/slack/provider.py are already touched): the lifespan calls slack_provider.start() only when the provider has an app (Slack enabled); otherwise it logs DEBUG slack_provider_start_skipped(reason=slack_disabled). Delete server/lifespan.py's _is_test_environment and its Slack-start guard (line ~303) once nothing else reads it; update tests/integration/server/test_lifespan_slack_start_log.py and test_lifespan.py, which patch it. Removes the false ERROR socket_mode_handler_missing and WARNING slack_provider_start_failed a Slack-off boot logs outside pytest; no remaining WARNING+ event changes level. Leave infrastructure/logging/setup.py's own _is_test_environment (pytest log suppression) alone.
8. Boot budget test (AC #5): see below.
9. Update the three tests that assert a demoted event (see Test matrix). Delete nothing else.

## Size gate
Estimate: ~19 production files, ~110 production LOC changed (about 35 one-line level swaps, ~45 lines of new phase-event fields), plus ADR text and 2 bin lines. Files exceed ~10; LOC and subsystems are within the spirit (one concern: log levels) but it touches server, infrastructure, integrations, jobs, packages, modules and bin. Recommended: ONE PR with a size exception (precedent: TASK-112.1 and TASK-156 exceptions for one-line swaps), because the AC #5 bound can only pass once everything is demoted, so no slice can land first alone. Fallback split if the human prefers: 28.4 (ADR, lifespan, manager, services, deploy-checks, budget test with the bound set at the post-slice-1 count) then a new subtask for the per-item swaps in step 6 and 7 that tightens the bound. Mechanical vs behavior: level swaps are one kind of change; the phase-event counts are the only behavior addition.

## Test matrix (names per testing-standards)
- tests/integration/server/test_server_boot_info_event_budget.py (new, AC #5): boots the real create_app on ENVIRONMENT=ci in a subprocess (pytest suppresses logging in-process: setup.py:197-199, and structlog.testing.capture_logs sees nothing once create_app reconfigures structlog, both verified). The probe module tests/integration/server/boot_probe.py patches the configure_logging name in server.configuration.host_configuration to add a capturing root handler, runs the lifespan with TestClient and prints (level, logger, event) rows as JSON. Asserts: (a) INFO records excluding configuration_slice are <= 10 (measured expectation 9: application_startup, core_services_initialized, security_services_initialized, directory_provider_initialized, feature_plugins_loaded, i18n_initialized, feature_integrations_registered, plugin_configuration_summary, scheduled_tasks_skipped; configuration_summary makes 10); (b) no INFO event name other than configuration_slice appears twice; (c) the configuration_slice count equals the length of configuration_summary.slices; (d) no WARNING+ record from this task's event list. Subprocess over in-process because the console renderer in ci and the pytest suppression make in-process capture unreliable; the cost is ~2 s.
- Update: tests/unit/server/test_server_configured_systems_read.py:132-141 (event now debug), tests/unit/packages/oncall_sync/test_oncall_sync_package_init.py:84 (level debug), tests/unit/jobs/test_scheduled_tasks.py:424 (debug), tests/integration/server/test_lifespan_scheduler_start.py:85,101 (add jobs field if asserted by args; they check names only).
- New unit tests in the existing files for the phase events: lifespan security/directory/i18n events carry their counts at INFO and the started/skipped lines at DEBUG (tests/integration/server/test_lifespan.py style), manager emits one feature_integrations_registered with counts (tests/unit/server/plugins/test_server_plugins_manager_registration_counts.py), webhook import lines are DEBUG (tests/unit/modules/webhooks/test_webhooks_pattern_log_levels.py).
- Failure case: a failing phase still logs its ERROR/CRITICAL (existing test_lifespan_plugin_boot_failure.py, test_lifespan.py:157 unchanged and green); boundary: security_services_initialized with issuer_count=0.

## AC traceability
AC1 -> notes inventories (local measured now, production by the human's query) | AC2 -> step 0 | AC3 -> steps 2-4, 6 + phase-event tests | AC4 -> step 5 plus the rg evidence below | AC5 -> boot budget test | AC6 -> verification.

## AC #4 evidence (rg --hidden over bin/, terraform/, .github/, app/tests, Makefile)
- bin/deploy-checks.zsh:95,113,158 match configured_systems_built: re-keyed (step 5). Line 147 webhook exclusion regex stays valid: those lines still print plain at import (see OQ4).
- terraform: only two metric filters exist (terraform/alarms.tf: sre_bot_error, sre_bot_warning, patterns in terraform/local.tf:16,26): raw-text matches on error/exception (skipping level warning|info) and on WARNING/level warning. No filter names an INFO event, so no demotion changes a metric. Hazard: a DEBUG line containing the word error or exception is not skipped by the info skip rule, so it would count when DEBUG is enabled; new DEBUG events avoid those words in names and field names (TASK-94 removes the hazard by matching fields).
- .github: no match. app/tests: the five assertions above.

## Assumptions and doubts (verify during implementation)
1. Cardinalities in production beyond ci come from code reading (the researcher's table), not a run: the human's query supplies the truth; re-measure ci after the swaps.
2. The probe's capture handler sees structlog dicts in record.msg through ProcessorFormatter.wrap_for_formatter; verify first, fall back to parsing the formatter output.
3. A ci boot outside pytest logs ERROR socket_mode_handler_missing (provider.start() with Slack disabled and socket_mode true) and WARNINGs; not this task's to change (no level change to WARNING+); the budget test ignores levels above INFO, and I record it as a possible follow-up (provider.start should skip when disabled).
4. registered_pattern etc. at DEBUG still print: structlog unconfigured at import prints every level (verified: a debug call before configuration printed). The level change is the AC but removes no printed line until TASK-168.
5. scheduled_tasks.run_continuously job count API: use schedule.get_jobs() (verify).

## Blast radius and rollback
Merge to main deploys. Behavior change is log volume only: no request path, no config, no schema. Risk: someone's eyes or an alarm on a removed INFO line; the rg above found only deploy-checks. One git revert restores everything. Manual-check rule does NOT apply (no terraform, task definition, IAM, SSM parameter or environment name change). Post-merge: run zsh bin/deploy-checks.zsh post summary and compare the boot INFO count (query in notes) with the baseline.

## Ordering
Starts after TASK-28.2 merges (and is deployed so logger and level fields exist in production for the inventory query) and TASK-156's post-deploy summary check passes. Independent of TASK-94, 163. Ripples: TASK-94 (no filter depends on a startup event), TASK-168 (add AC: remove the webhook exclusion; examples.py already deleted here), TASK-164 (deploy-checks boot key becomes core_services_initialized when it moves to CI), TASK-28.3 (no overlap).

## Verification (verbatim gate rule)
During implementation, run ruff and the targeted test files only. At the very end, run full mypy and fix what it finds, then full pytest alone, once each, never in parallel, rerunning only on a real error: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; cd app && uv run pytest tests --ignore=tests/smoke. Also run make check-import-contracts and make check-settings-key-ownership. Full mypy currently reports 41 pre-existing errors in untouched files (modules/*, infrastructure/i18n/service.py and resolvers.py, features/incident/scheduling/adapters/google_calendar.py, features/incident/meet/adapters/google_meet.py, integrations/slack/channels.py): judge only the touched files; note that several demotion edits touch modules/webhooks and infrastructure/i18n/service.py, so compare mypy output on those files against the 41 and do not fix the existing errors. No smoke tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-03 (from TASK-28.2's approved plan): uvicorn contributes four startup INFO lines (now JSON), not this task's to change; the webhook import-time lines belong to TASK-168; liveness access hits are DEBUG after 28.2.

## Planning notes 2026-11-03 (proposed plan, nothing implemented)

### AC #1 local inventory (planning-time, BEFORE the change): ENVIRONMENT=ci, real create_app plus TestClient lifespan, pytest-env values, fake AWS credentials, run outside pytest. Startup records before the first request (shutdown excluded). To be re-measured after the change.
INFO 78 total. Per event (count): configuration_slice 27, configuration_summary 1; application_startup 1; core_service_resolved 3, core_services_initialized 1, configured_systems_built 1, initialized_record_store 1; security_services_initialization_started 1; directory_provider_initialization_started/warmup_skipped/completed 3; slack_provider_initialized 1; plugin_manager_created 1; feature_plugins_loaded 1; plugin_requirements_resolved 1; i18n: i18n_resource_registered 2, i18n_resources_collected 1, initialized_yaml_loader 4, initialized_translator 1, loaded_translations 8, loaded_all_translations 1, translator_created_with_preload 1, i18n_initialization_started 1, i18n_initialization_completed 1, i18n_healthcheck_passed 1, i18n_initialization_completed_and_healthy 1; slack_commands_registered 1, feature_routes_registered 1, feature_startup_warmup_completed 1, feature_integrations_registered 1; plugin_configuration_summary 1; legacy_slack_commands_registered 1; initializing_slack_app 1; scheduled_tasks_skipped 1; botocore (foreign) 4 (Found credentials x2, Found endpoint x2). event_handlers_registered does not fire (no dispatcher passed).
WARNING 5 (security_setting_weakened, incident_comms_registration_skipped, slack_disabled_skipping_init, slack_provider_app_unavailable, slack_provider_start_failed); ERROR 1 (socket_mode_handler_missing, an artifact of running outside pytest with Slack off). Not in ci: audit service init, jwks lines, access/oncall plugin lines (plugins off), scheduled jobs registered, slack app lines.
Plain pre-configuration lines at import: 13 (10 registered_notification_pattern, 1 no_handlers_found_in_module, 1 notification_handlers_initialization_complete, 1 registered_pattern); all INFO-looking, none JSON.
Expected after: 10 INFO excluding configuration_slice (listed in the plan) + 27 slices.

### AC #1 production inventory: the human runs this read-only (aws logs start-query / get-query-results, jq), the agent reads the output. Run it after TASK-28.2 is deployed (the logger field and JSON uvicorn lines exist then), and again after this task deploys. It finds the latest boot stream and counts every record 120 s before to 180 s after its application_startup event, excluding access lines; no secrets printed (names and counts only).
zsh -c '
R=ca-central-1 LG=/ecs/sre-bot-app
q() { local id st; id=$(aws logs start-query --region $R --log-group-name $LG --start-time $1 --end-time $2 --query-string "$3" --query queryId --output text); until [[ $(aws logs get-query-results --region $R --query-id $id --query status --output text) == Complete ]]; do sleep 2; done; aws logs get-query-results --region $R --query-id $id --output json | jq -c ".results[] | map({(.field): .value}) | add | del(.\"@ptr\")"; }
now=$(date -u +%s); from=$((now-172800))
row=$(q $from $now "filter event = \"application_startup\" | stats max(toMillis(@timestamp)) as t by @logStream | sort t desc | limit 1")
stream=$(print -r -- $row | jq -r ".\"@logStream\""); t=$(print -r -- $row | jq -r ".t|tonumber|floor"); s=$((t/1000-120)); e=$((t/1000+180))
print "stream=$stream window=$(date -u -d @$s +%FT%TZ)..$(date -u -d @$e +%FT%TZ)"
q $s $e "filter @logStream = \"$stream\" and @message not like /uvicorn.access/ and @message like /^\\s*\\{/ | stats count() as n by level, event | sort level asc, n desc | limit 200" | tee tmp/boot-inventory-json.txt
print "non-JSON lines in the window:"
q $s $e "filter @logStream = \"$stream\" and @message not like /^\\s*\\{/ | stats count() as n" | tee -a tmp/boot-inventory-json.txt
' 
(run from the repo root; tmp/ is gitignored. If the first row is empty, widen from=$((now-604800)).)

### AC #2 proposed text for decisions/observability.md (new paragraph after "Logging starts in the configuration phase"; to be edited in the working tree first)
**Startup logging rule.** Each lifespan phase ([lifecycle.md](lifecycle.md)) logs exactly one INFO event that names the phase (`phase` field) and carries the counts that prove it completed (`count`, `plugins`, `issuer_count`, `resource_count`), at a stable event name. Per-item registration and construction detail (one line per service, plugin, command, route, job, locale file, issuer or pattern) is DEBUG, so enabling DEBUG reconstructs the sequence without changing code. Configuration is reported only by the generated `configuration_slice`, `configuration_summary` and `plugin_configuration_summary` events ([configuration.md](configuration.md)); a phase event never repeats a setting value. WARNING, ERROR and CRITICAL events keep their level whatever the phase; a failing phase is logged by its failure event, never by a missing success event. A boot is expected to emit at most one INFO event per phase beside the configuration events, and a boot test holds a ci boot to that bound. Library loggers (botocore) are held at WARNING by the pipeline; slack_sdk and uvicorn lines keep their own levels because deploy checks match them. Sources: OpenTelemetry defines DEBUG as a debugging event and INFO as "an event happened" ([logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)); the OWASP Logging Cheat Sheet lists start-ups, shut-downs and logging initialization as events to log, and warns "it is important not to log too much, or too little" and of "alarm fog" ([OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)); Spring Boot logs one INFO "Started X in Y seconds" line and turns detail on only in debug mode, which raises a selection of core loggers rather than every message ([Spring Boot logging](https://docs.spring.io/spring-boot/reference/features/logging.html)); ASP.NET Core's generic host exposes started, stopping and stopped lifetime events as the phase boundaries and lets a host suppress its status messages ([Generic Host](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/host/generic-host)); structlog and the standard library filter by level per logger, which is what makes library loggers adjustable without touching call sites ([structlog standard library](https://www.structlog.org/en/stable/standard-library.html)).
Changes entry: "2026-11-03: startup logging rule: one INFO event per lifespan phase with counts, per-item detail at DEBUG, configuration only in the generated summaries (TASK-28.4)." Caveat for the review: the Spring and ASP.NET pages were read for their startup-message behaviour only; the per-phase count is this project's rule, not copied from them.

### Open questions, recommendation each
OQ1 Size: one PR with a size exception, or split. Recommend one PR (plan "Size gate"; doc-11 standing rule, precedent rows 9.9b.1 and 9a). 
OQ2 configured_systems_built: demote to DEBUG and re-key deploy-checks on core_services_initialized (recommend; task text lists it as a per-step line, event exists in the running revision, fewer INFO), versus keep it INFO and change no bin file. Both satisfy AC #4.
OQ3 configuration_slice events (27 at ci) stay INFO: configuration.md (Accepted 2026-10-29) mandates one event per slice under a summary; they are the AC #2 "generated summaries" and are excluded from the bound but pinned to the summary's slice list.
OQ4 Webhook lines: lowering them to DEBUG is required by the AC but prints the same 13 plain lines until TASK-168, because structlog is unconfigured at import (verified). Recommend: do it, delete dead examples.py, keep deploy-checks line 147 exclusion, and state this in the PR. Do not install configuration earlier (observability.md forbids import-time side effects).
OQ5 Foreign loggers: botocore to WARNING in the pipeline (recommend; 4 INFO lines in ci, per client in production; DEBUG recovers them). slack_sdk lines left alone, although the task description names them: deploy-checks.zsh:127,157 match "session has been established" and "on_error invoked" as the Socket Mode health evidence.
OQ6 Bound: <= 10 INFO excluding configuration_slice, and no repeated INFO event name. Recommend exactly this (measured 9 plus the configuration_summary); a new phase event raises the number in the same PR as a deliberate act.
OQ7 security phase when no issuer: log security_services_initialized with issuer_count=0 so the phase has its one event (small behavior addition). Recommend yes.
OQ8 provider.start() logs ERROR socket_mode_handler_missing when Slack is disabled but socket_mode is true, outside pytest. Not changed here (no WARNING+ change); recommend a follow-up task, human to create.
OQ9 scheduled jobs: confirm that per-job lines go DEBUG and scheduled_tasks_started carries jobs=N. Recommend yes.

### Ripples
TASK-94: no terraform metric filter keys on a startup event (alarms.tf, local.tf checked); the DEBUG-with-"error"-word hazard is noted above. TASK-168: add AC to remove deploy-checks line 147 exclusion and the plain import lines; examples.py is gone after this task. TASK-164: its CI port reads the new boot key core_services_initialized. TASK-28.3: none. TASK-163: none (terraform only). doc-11: update row 9a.2 with this plan (human edits; doc-11 is untracked and never committed).

2026-11-03: plan approved (human), OQ1-OQ9 as recommended: OQ1 one PR with a size exception; OQ2 configured_systems_built DEBUG, deploy-checks re-keyed on core_services_initialized (present since before 2a73d00a); OQ3 configuration_slice stays INFO; OQ4 webhook lines DEBUG, examples.py deleted, deploy-checks exclusion kept until TASK-168; OQ5 botocore WARNING, slack_sdk untouched; OQ6 bound <= 10 INFO excluding configuration_slice, no repeated INFO name; OQ7 security_services_initialized with issuer_count=0; OQ8 folded in (plan step 7a: Slack start only when enabled, lifespan _is_test_environment guard deleted; closes the doc-11 carry-over follow-up); OQ9 scheduled_tasks_started jobs=N. TASK-28.2 merged and deployed 2026-11-03 (#1814, 90ed5968). observability.md Startup logging rule and lifecycle.md pointer written on main's working tree 2026-11-03, carried by this task's branch. Ripples recorded on TASK-168, TASK-164, TASK-94. AC #1 production half waits for the human's inventory query (notes above).
<!-- SECTION:NOTES:END -->
