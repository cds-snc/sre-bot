---
id: TASK-112.4
title: >-
  Scheduler run switch [scheduler] enabled, started independent of the Slack
  transport; guard against env and ENVIRONMENT plugin switches
status: In Progress
assignee: []
created_date: '2026-10-26T15:04:00Z'
updated_date: '2026-10-26T17:48:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-112.3
references:
  - decisions/reliability.md
  - decisions/lifecycle.md
  - decisions/configuration.md
  - decisions/transport-slack.md
  - decisions/plugins.md
parent_task_id: TASK-112
priority: medium
type: feature
ordinal: 444000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice B of TASK-112 (split from TASK-112.3 on 2026-10-26, human). The scheduler is a host capability composed like a transport (decisions/reliability.md), started in lifespan phase 6 alongside, not inside, the transports (decisions/lifecycle.md). Today server/lifespan.py starts it only when ENVIRONMENT == "production" and only inside the "Slack app available" branch, handing it the Bolt app so one legacy job (notify_stale_incident_channels) can use bot.client; and an _is_test_environment() (sys.modules, prohibited by decisions/configuration.md) guard skips it under pytest.

This task:
- SchedulerSettings (jobs/settings.py) becomes a ConfigurationSlice on a [scheduler] table: enabled (false in base, true in production) and the default Tier-2 lease TTL. Taken out of TASK-111.13's scope.
- server/lifespan.py starts the scheduler on [scheduler] enabled, independent of the Slack transport: no ENVIRONMENT comparison, no Bolt app passed in, no _is_test_environment() guard on the scheduler start (ci.toml leaves it off). The guard on the Slack start stays (follow-up, not created).
- The legacy stale-channel job takes the outbound Slack Web API client from integrations/slack (decisions/transport-slack.md: outbound-only callers use the client, never the runtime) and is registered only when the [slack.tenant] entry is configured (a vendor's tenant entry enables it, decisions/configuration.md); otherwise it logs it was skipped. TASK-145.9 later moves the job into the incident package (register_background_jobs).
- Guard (two rules in bin/check_settings_key_ownership.py, the one CI script for such bans per decisions/configuration.md): a flat settings 'enabled' switch, and an ENVIRONMENT comparison deciding whether a plugin or the scheduler runs (server/lifespan.py, server/plugins/, packages/, features/, jobs/; server/configuration/ and legacy modules/ excluded).
- ADRs: reliability.md (scheduler independent of transports), lifecycle.md (tolerated item closed), plugins.md Checks (guard).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 [scheduler] enabled decides whether scheduled jobs start (false in base, ci and local; true in production); server/lifespan.py has no ENVIRONMENT comparison; production still starts its scheduled jobs (test pins production.toml)
- [x] #2 The scheduler starts in the transport phase independent of the Slack app: it starts with the Slack transport off or its app unavailable, receives no Bolt app, and has no _is_test_environment() guard (tests)
- [x] #3 The stale-incident-channels job uses the integrations/slack Web API client and is registered only when [slack.tenant] is configured; otherwise a skip is logged with the reason (tests)
- [x] #4 A CI check fails on a flat settings 'enabled' switch or an ENVIRONMENT comparison deciding whether a plugin or the scheduler runs in server/lifespan.py, server/plugins/, packages/, features/ or jobs/ (bin check tests)
- [x] #5 decisions/reliability.md, lifecycle.md and plugins.md record the switch, the transport-independent start and the guard; TASK-111.13 no longer lists the scheduler
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STATUS: written 2026-10-26 from TASK-112.3's Slice B, revised after the human asked that the scheduler not depend on the Slack app; APPROVED 2026-10-26 (human). Branch from main c3de2f3c (TASK-112.3 merged as #1789). Deploy check: named task check 'scheduler' in bin/deploy-checks.zsh, which deletes the 'plugins' check (112.2 and 112.3 Done).

CALL SITES (app/)
jobs/settings.py:8-17 SchedulerSettings(InfrastructureSettings), flat DEFAULT_TIER2_LEASE_TTL_SECONDS; reader jobs/scheduled_tasks.py:15,88 (get_scheduler_settings name kept). jobs/scheduled_tasks.py:99 init(bot, register_plugin_jobs, service_scopes); :112-115 notify_stale_incident_channels scheduled with client=bot.client (the only use of bot). server/lifespan.py:111-124 _start_scheduled_tasks(bot, host, ...) with host.environment != "production" at :119; :327-336 start nested in the "slack app available" branch, guarded by _is_test_environment() at :333; :338-342 else branch sets scheduled_stop_event None; :343 Slack start guard STAYS; :55 _is_test_environment stays. server/configuration/host_configuration.py (_validate_slices / HostConfiguration, next to slack_transport). integrations/slack/client.py:37 get_slack_web_client(); integrations/slack/settings.py:69 tenant (None = Slack unconfigured). bin/check_settings_key_ownership.py. Tests: tests/unit/jobs/test_jobs_settings.py, tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py:66, tests/unit/bin/test_bin_settings_key_ownership_check.py, tests/integration/server/test_lifespan.py:163 and lifespan tests asserting scheduled_tasks_skipped.
Other ENVIRONMENT comparisons in scope: only server/configuration/host_configuration.py:74 (dev-bypass refusal, security; excluded by path).

SIZE: about 8 production files (jobs/settings.py, jobs/scheduled_tasks.py, server/lifespan.py, host_configuration.py, config/base.toml, config/production.toml, bin/check_settings_key_ownership.py, plus 3 ADRs), about +130/-45 LOC. One subsystem (host runtime and its CI check). Gate passes.

STEPS (TDD)
B1 tests first:
- tests/unit/jobs/test_jobs_scheduler_settings_files.py: SchedulerSettings is a ConfigurationSlice on [scheduler]; reads enabled and default_tier2_lease_ttl_seconds (1800); SCHEDULER__ENABLED overrides; unknown key fails (extra=forbid).
- config-files pin (in the existing server configuration files-load test): base false, production true, ci and local not enabled.
- tests/integration/server/test_lifespan.py (or tests/unit/server/test_server_lifespan_scheduler_start.py): starts when enabled with the Slack transport off; starts when enabled and the Slack app failed to initialise; not started when disabled (scheduled_tasks_skipped reason=scheduler_disabled); production-like HostInfo with the scheduler off does not start (no ENVIRONMENT dependence); stopped at shutdown.
- tests/unit/jobs/test_jobs_scheduled_tasks_init.py: init takes no bot; with [slack.tenant] set the stale-channel job is scheduled and resolves get_slack_web_client() per run (not at init); with no tenant it is not scheduled and scheduled_job_skipped job_name=notify_stale_incident_channels reason=slack_not_configured is logged at info.
- bin check tests per rule (B5).
B2 jobs/settings.py: SchedulerSettings(ConfigurationSlice), table ('scheduler',), env prefix SCHEDULER__, enabled: bool = False, default_tier2_lease_ttl_seconds: int = 1800 (described), get_scheduler_settings() kept. Drop the flat DEFAULT_TIER2_LEASE_TTL_SECONDS (production sets none, doc-14); delete its row in test_configuration_settings_production_names.py. base.toml [scheduler] enabled = false, default_tier2_lease_ttl_seconds = 1800; production.toml [scheduler] enabled = true.
B3 jobs/scheduled_tasks.py: init(register_plugin_jobs, service_scopes) without bot; the stale-channel job is wrapped so it calls notify_stale_incident_channels(get_slack_web_client()) per run, scheduled only when get_slack_settings().tenant is set. Dead code: the bot parameter and its docstring line go.
B4 host_configuration.py: HostConfiguration gains scheduler: SchedulerSettings (validated with the host slices). lifespan.py: _start_scheduled_tasks(scheduler, logger, service_scopes), no HostInfo, no bot; called once after the Slack block (phase 6: transports then scheduler), not inside the "slack app available" branch, with no _is_test_environment() condition; the else branch no longer touches scheduled_stop_event. Delete the now-unused host parameter.
B5 bin/check_settings_key_ownership.py, two rules: plugin-switch (a settings class that is not a ConfigurationSlice declares a field named enabled, under server/, packages/, features/, jobs/); environment-gate (an ast.Compare against an environment/ENVIRONMENT name or attribute, or os.environ["ENVIRONMENT"], in server/lifespan.py, server/plugins/, packages/, features/, jobs/; server/configuration/ and modules/ excluded by path). Tests: one violating fixture per rule, clean tree, path exclusions, real tree clean.
B6 docs and backlog: ADR text written at planning (2026-10-26): reliability.md (transport-independent start, outbound client, tenant gating, Checks lines), lifecycle.md (tolerated item now names the Slack-branch start), plugins.md (Checks line). At implementation: close lifecycle.md's tolerated scheduled-tasks item and update its Current-state line 20, with a Changes line. TASK-111.13's title already drops the scheduler (2026-10-26).

AC TRACEABILITY: AC1 -> B1, B2, B4 -> settings and files-pin tests, lifespan disabled/production tests. AC2 -> B1, B4 -> lifespan Slack-off and Slack-failed tests. AC3 -> B1, B3 -> scheduled_tasks init tests. AC4 -> B5 -> bin check tests. AC5 -> B6 -> doc diff. AC6 -> gates.

TEST MATRIX: happy (enabled starts; tenant set schedules the stale job), boundary (Slack off but scheduler on; Slack init failed; tenant absent), failure (unknown [scheduler] key; guard violations), no-ENVIRONMENT (production HostInfo, scheduler off).

ASSUMPTIONS TO VERIFY: (1) no production .env line SCHEDULER__* or DEFAULT_TIER2_LEASE_TTL_SECONDS (doc-14; deploy check prints blob_where); a stray SCHEDULER__ unknown name would fail boot, so check pre-merge. (2) No legacy job other than notify_stale_incident_channels needs the Bolt app (verified: :112-115 is the only bot use). (3) integration_healthchecks and provision_aws_identity_center need no Slack. (4) Under pytest the scheduler stays off because ci.toml/base leave it off; tests that enable it stub scheduled_tasks.run_continuously.

BLAST RADIUS AND ROLLBACK: production behaviour unchanged except ordering: jobs now start even if the Slack app fails to initialise (intended). A wrong production.toml value silently stops all jobs: pinned by test and the post-scheduler deploy check. One git revert restores; no terraform or SSM change. Human: delete any DEFAULT_TIER2_LEASE_TTL_SECONDS line in app/.env.example; local scheduled jobs need SCHEDULER__ENABLED=true in app/.env.

DEPLOY CHECK (new phase post-scheduler, human extends /workspace/tmp/deploy-checks.zsh): post-plugins checks plus scheduled_tasks_started count >= tasks since the deploy; no scheduled_tasks_skipped; no scheduled_job_skipped for notify_stale_incident_channels; running_scheduler_heartbeat on every task within 6 minutes; feature_background_job_scheduled listed; no configuration_invalid; blob_where for DEFAULT_TIER2_LEASE_TTL_SECONDS and SCHEDULER.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26: the deploy checks are versioned in bin/deploy-checks.zsh (TASK-112.3); this task's post-deploy check is a named task check 'scheduler' (zsh bin/deploy-checks.zsh post scheduler), not a post-scheduler phase, and it deletes the 'plugins' check if 112.2 and 112.3 are Done by then.

2026-10-26 implementation (plan approved by the human 2026-10-26; working tree on main c3de2f3c, branch task-112.4-scheduler to be created by the human). SchedulerSettings is the [scheduler] ConfigurationSlice (enabled false in base, true in production.toml; default_tier2_lease_ttl_seconds 1800); DEFAULT_TIER2_LEASE_TTL_SECONDS retired (pin row deleted; audit HINTS entry so env-checks says delete, not a SCHEDULER__ rename). HostConfiguration carries the slice; lifespan starts the scheduler after the Slack block with no ENVIRONMENT comparison, no Bolt app and no _is_test_environment() guard (the Slack start guard stays). init(register_plugin_jobs, service_scopes); the stale-channel job runs notify_stale_incident_channels_job, which builds the integrations/slack Web API client per run, scheduled only with [slack.tenant], else scheduled_job_skipped reason=slack_not_configured. Two rules in bin/check_settings_key_ownership.py: plugin-switch (a non-slice settings class under server/lifespan.py, server/plugins/, packages/, features/, jobs/ declaring an enabled field, or a <NAME>_enabled field without env_prefix; ACCESS_SYNC_RECONCILIATION_ENABLED, a prefixed in-plugin job toggle, passes: TASK-166's) and environment-gate (any comparison against environment/ENVIRONMENT there). Implementation decision: pytest-env pins SCHEDULER__ENABLED=false, as 112.3 pins the access plugins off, so a developer's app/.env never starts the real jobs thread in tests (configuration.md Changes). ADRs: lifecycle.md current state and tolerated item closed, plugins.md Checks wording matches the rule, reliability.md and configuration.md Changes. Deploy check: named task check 'scheduler' in bin/deploy-checks.zsh; the 'plugins' check is deleted (112.2 and 112.3 Done). Gates: ruff clean; mypy 47 errors = baseline, none in touched files; pytest tests --ignore=tests/smoke 5778 passed (was 5751); make check-import-contracts 13 kept; make check-settings-key-ownership OK. Human: make env-checks before merge (no SCHEDULER__* or DEFAULT_TIER2_LEASE_TTL_SECONDS in app/.env.example, app/.env, Codespaces, blobs); pre at merge; after deploy zsh bin/deploy-checks.zsh post scheduler (rerun after 6 minutes for the heartbeat). Parent TASK-112 ACs 3 and 4 checked.
<!-- SECTION:NOTES:END -->
