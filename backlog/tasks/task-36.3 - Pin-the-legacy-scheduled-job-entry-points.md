---
id: TASK-36.3
title: Pin the legacy scheduled-job entry points
status: Done
assignee: []
created_date: 2026-09-28 14:36
updated_date: '2026-11-09T17:44:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - https://github.com/cds-snc/sre-bot/issues/1613
parent_task_id: TASK-36
priority: high
ordinal: 287000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pin the 5 scheduled-job rows of the TASK-36 inventory (app/tests/integration/legacy_surface/INVENTORY.md, 'Scheduled job entry points'): the 3 legacy jobs scheduled in jobs/scheduled_tasks.py init() (provision_aws_identity_center over modules.aws.identity_center, notify_stale_incident_channels from modules.incident, and spending.execute_spending_data_update_job from modules.aws.spending) and the 2 plugin-registered jobs (access_sync_reconciliation and oncall_sync, registered through the register_background_jobs hookimpl). They are the before/after check for the TASK-52 scheduler move and the TASK-145.9 and TASK-88 rebuilds. Invoke each job's entry point directly with faked integrations and assert on its observable effects; do not start the scheduler. The host-owned Tier-1 jobs (scheduler_heartbeat, integration_healthchecks) are not inventory rows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each legacy job entry point in the TASK-36 inventory has a pinning test with faked integrations
- [x] #2 Tests live in app/tests/integration/legacy_surface/ and run in the normal gate
- [x] #3 The TASK-36 inventory marks each job row pinned by this task
- [x] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #5 The TASK-36 inventory's five scheduled-job rows show the current Defined-at lines, rebuild tickets and targets (stale refs and superseded TASK-124.2/TASK-123 corrected) alongside the Pinned-by cells
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope and findings (re-verified against main code, 2026-11-06)

Pin the observable effects of the five inventory jobs by calling each entry point directly with faked integrations. No production code changes. The scheduler is never started. Tests only, plus INVENTORY.md.

Current location of each job (the inventory refs are stale):
1. provision_aws_identity_center: schedule at app/jobs/scheduled_tasks.py:147 (every 2h, wrapped by _tier2 at :122); entry point app/jobs/scheduled_tasks.py:211, which calls modules/aws/identity_center.py:86 synchronize(enable_user_create=False, enable_membership_create=True, enable_membership_delete=True). Edges: infrastructure.directory get_directory_provider (modules/provisioning/groups.py:107, users.py:47) and build_identity_center_adapter (modules/aws/identity_center.py:8, provisioning/groups.py:142, users.py:61).
2. notify_stale_incident_channels: schedule at jobs/scheduled_tasks.py:150-153 (daily 16:00, only if [slack.tenant]); entry point notify_stale_incident_channels_job at jobs/scheduled_tasks.py:165, which builds get_slack_web_client() per run and calls modules/incident/notify_stale_incident_channels.py:10. The body only uses integrations/slack/channels.py (get_channels :9, get_stale_channels :50, get_messages_in_time_period :69), INCIDENT_CHANNELS_PATTERN r"^incident-\d{4}-" (modules/incident/incident_helper.py:34) and integrations.sentinel log_to_sentinel. It never reads incident records, so the pin is independent of the record model.
3. spending.execute_spending_data_update_job: schedule at jobs/scheduled_tasks.py:156-159 (daily 00:00); entry point modules/aws/spending.py:256. Edges: build_organizations_adapter and build_cost_explorer_adapter (spending.py:51-52), get_spreadsheet_provider (spending.py:242, update_values(sheet_id, "Sheet1", values)), sheet id from get_cloud_operations_spending_settings().sheet_id (features/cloud_operations/spending/settings.py).
4. access_sync_reconciliation: still in packages/access/sync/__init__.py (not moved; TASK-124.1 open). Hookimpl register_background_jobs :85 (register_daily, no lease_ttl, so Tier-1 without lease; the inventory says :94). Entry point _run_reconciliation_job :48. It loops get_access_runtime_config().platforms and calls get_access_sync_coordinator().sync_platform(platform=, dry_run=False). Note: access.* plugins are disabled in production since TASK-112.2, so this job is dormant there; the code still exists and moves in 124.1.
5. oncall_sync: still in packages/oncall_sync/__init__.py (NOT moved; TASK-124.2 is archived as superseded, TASK-123 superseded by TASK-146.1, on-call re-cut in TASK-146/146.2). Hookimpl register_background_jobs :40 (register_interval 5 min, no lease; the inventory says :34). Entry point _run_oncall_sync :25 -> providers.get_oncall_sync_service().sync_all() (service.py:46). Edges are the ports in packages/oncall_sync/ports.py (OnCallScheduleProvider, UserGroupSyncTarget, UserRotationsProvider).

Not in the inventory, not pinned: the incident legacy upgrade job (features/incident/response/plugin.py:33, job name incident_legacy_upgrade, registered via register_background_jobs with a lease_ttl). It is new since the inventory was written, has its own tests (TASK-145.5.7) and is deleted by TASK-145.13. The host Tier-1 jobs stay out as the task says. Inventory change proposed for it: none (add a one-line note under the table that it exists and is out of scope).

Wrapper decision (Tier-2 lease): BYPASS. Call the unwrapped entry points. The lease (acquire, skip when held, release, lease-key names, TTL) belongs to the scheduler runtime, which TASK-52 and TASK-65 are about to rewrite (jobs/scheduled_tasks.py _tier2 becomes the registry lease_ttl keyword). It is already pinned by tests/unit/jobs/test_scheduled_tasks.py (TestTier2Wrapper, init lease keys, cadence) and test_jobs_scheduled_tasks_registry_lease.py. Pinning it again in the entry-point tests would make the 52/65 PRs rewrite these pins. No new registration or cadence tests here for the same reason.

## Design rules
- Assert only effects visible at the integration edge: Slack Web API calls, Sentinel events, identity-store membership writes, spreadsheet writes, user-group syncs, platform sync calls. Never assert logger calls, private helper calls or call order inside a job.
- Each test file imports its entry point in ONE line at the top (an alias such as run_stale_channel_job), so the rebuild PR (145.9, 88, 124.1, 146.2) changes that import and the edge-patch fixture, not the tests.
- Reuse the legacy_surface harness conventions: pytestmark = pytest.mark.integration, FakeSlackClient from tests/factories/slack_bolt.py, WebClient.api_call routed into the fake (as legacy_handler_harness does in conftest.py:261-273), sentinel_client.send_event recorded. Do not edit shared factories used by siblings; the per-channel reply behaviour is a small FakeSlackClient subclass local to legacy_surface.
- Time: get_stale_channels uses the real clock with a 14-day window, so channels get created timestamps relative to now (20 days, 3 days). No clock patching.

## Ordered steps (stale-channel first: it gates 145.9)

Step 1. app/tests/integration/legacy_surface/conftest.py (additive only): extract a reusable fixture routed_slack_client that patches WebClient.api_call into a per-channel-aware FakeSlackClient subclass (conversations_history replies keyed by the channel kwarg; conversations_list pages keyed by cursor) and a sentinel_events recorder, and gives a bot token via the Slack settings so get_slack_web_client() builds. The existing legacy_handler_harness is left untouched (no refactor of sibling fixtures).

Step 2. app/tests/integration/legacy_surface/test_incident_stale_channel_job_run.py (AC 1, 2). Calls notify_stale_incident_channels_job. Observable effects only: which channels get chat_postMessage, which are skipped, joins, Sentinel. Tests (Test matrix below).

Step 3. app/tests/integration/legacy_surface/test_aws_identity_center_provision_job_run.py (AC 1, 2). Fakes: FakeDirectoryProvider (list_groups_with_members, list_users) patched at modules.provisioning.groups/users get_directory_provider; FakeIdentityCenterAdapter (list_users, list_groups_with_memberships, create_group_membership, delete_group_membership) patched at the three bound build_identity_center_adapter names. Asserted effects: memberships created/deleted per group and user, no user created or deleted, only groups prefixed AWS- considered.

Step 4. app/tests/integration/legacy_surface/test_aws_spending_data_update_job_run.py (AC 1, 2). Fakes: organizations and cost-explorer adapter doubles returning OperationResult (pattern from tests/unit/modules/aws/test_spending_handler.py), spreadsheet provider double, sheet id via CLOUD_OPERATIONS_SPENDING__SHEET_ID with cache clear. Asserted effects: one update_values(sheet, "Sheet1", rows) with a header row plus one row per account-and-service for the accounts and costs, no write when a lookup fails, no write when no accounts or no spend, write failure does not raise. Do not assert exchange-rate arithmetic (rates dict is a stale-prone internal) beyond the presence of the converted-cost column.

Step 5. app/tests/integration/legacy_surface/test_access_sync_reconciliation_job_run.py (AC 1, 2). Patch get_access_runtime_config and get_access_sync_coordinator on packages.access.sync with a runtime config of two platforms and a recording coordinator (sync_platform is the application API also used by the HTTP route, not a job internal). Asserted: every configured platform synced once with dry_run False; behaviour when a platform's sync returns a failure result is pinned only after verifying today's behaviour (doubt D3).

Step 6. app/tests/integration/legacy_surface/test_oncall_sync_job_run.py (AC 1, 2). Build a real OnCallSyncService over fakes of the ports and patch packages.oncall_sync.providers get_oncall_sync_service (the documented swap point). Asserted: each rotation's group set to its on-call email, the schedule aggregate group to the union, schedule group skipped when a rotation fails, a rotation failure does not abort other schedules, user rotations synced by Slack user id.

Step 7. app/tests/integration/legacy_surface/INVENTORY.md (AC 3, 5): in the 'Scheduled job entry points' table fill the Pinned by cell of all 5 rows with the new test file; correct the Defined at cells to the lines above (jobs/scheduled_tasks.py:147, :150-153, :156-159 and entry points :211, :165, spending.py:256; access sync __init__.py:85/:48; oncall __init__.py:40/:25); fix Rebuild ticket cells: stale-channel row TASK-38 (after TASK-97) -> TASK-145.9, oncall row drops TASK-124.2 and TASK-123 (superseded) for TASK-146.2; fix the Target of oncall (app/features/oncall_sync/ is not decided: TASK-146 re-cut). Add the one-line note about incident_legacy_upgrade. Edit only the 5 rows and that note.

## AC traceability
- AC1 (each job pinned with faked integrations): Steps 2-6; tests listed in the matrix.
- AC2 (location and normal gate): Steps 2-6 in app/tests/integration/legacy_surface/, picked up by `pytest tests --ignore=tests/smoke`, named test_<domain>_<entity>_<action>.py.
- AC3 (inventory marks rows pinned): Step 7.
- AC5 (new, inventory reflects current code): Step 7.
- AC4 (gates): Verification section.
Every step maps to an AC; Step 1 is enabling work for AC1.

## Test matrix
test_incident_stale_channel_job_run.py
- happy: an incident-named channel older than 14 days with no user message in the window gets exactly one chat_postMessage carrying the bilingual 14-day notice and the three buttons (callback_id archive_channel; actions archive, schedule_retro, ignore) and a Sentinel sent_stale_channel_notification event naming that channel.
- skip: channel name not matching ^incident-\d{4}- is never joined or posted to; incident channel younger than 14 days is not nudged; incident channel with a user message ("team" key) in the window is not nudged.
- boundary: a window holding only bot/system messages (no "team" key) is still stale and is nudged; two pages of conversations_list (next_cursor) are both read; several stale channels each get one post.
- joins: every candidate channel is joined before its history is read.
- failure: conversations_list returning ok False posts nothing and does not raise; empty workspace posts nothing.
- Not pinned on purpose: abort-on-first-post-failure and exact copy beyond the 14 days/14 jours markers (not intended contract).
test_aws_identity_center_provision_job_run.py
- happy: a Google member missing from the AWS group (user exists in AWS) is added to that group; a member in the AWS group but not in the Google group is removed.
- boundary: Google user not in AWS is NOT created and not added; no AWS user is ever deleted; Google groups without the AWS- prefix and AWS groups without a Google match are untouched; AWS membership without a membership id is skipped.
- failure: directory listing failure or identity-store listing failure raises/aborts with no writes (verify exact current behaviour, pin only the no-writes effect).
test_aws_spending_data_update_job_run.py
- happy; accounts-lookup failure -> no write; cost lookup failure -> no write; no accounts -> no write; no spend -> no write; write failure does not raise; tags missing -> account kept as Unknown product and business unit (observable in rows).
test_access_sync_reconciliation_job_run.py
- happy: each configured platform reconciled once, not a dry run; no platforms -> no sync; a failing platform result: pin current behaviour after verification.
test_oncall_sync_job_run.py
- happy; gap in coverage (no on-call user) leaves group untouched; rotation failure skips the schedule group but syncs the others; user-rotation Slack ids synced; no schedules and no rotations -> nothing (edge of hookimpl, already unit-tested, not repeated).
Authorization and idempotency: not applicable (jobs have no caller); idempotency is covered by running an entry point twice in the identity-center and stale-channel tests and asserting a stable second-run effect only where the code is idempotent today (identity center second run with converged state makes no writes).

## Assumptions and doubts (each with how to verify)
- D1 FakeSlackClient replies are static per method, so per-channel history needs the local subclass. Verify by reading tests/factories/slack_bolt.py:56-84 (done: replies is a dict by method name).
- D2 get_slack_web_client() can build with an empty bot token under test settings (SlackSettings bot_token default SecretStr("")). Verify in Step 1; if it raises, set SLACK__BOT_TOKEN through monkeypatch and cache_clear on get_slack_settings.
- D3 Access sync: behaviour on a failed sync_platform result is not confirmed (the loop ignores the return value, so a failure on platform A does not stop platform B; an exception would). Verify by reading packages/access/sync/application.py:215 and running a throwaway call before writing the assertion.
- D4 Identity-center edges patched at from-import names in three modules; if a rebuild changes the factory the fixture is the only thing to change. Verify with `rg -n "build_identity_center_adapter|get_directory_provider" app/modules app/packages`.
- D5 Spending: generate_spending_data reads datetime.now() for the 12-month window; fakes return the same entry for every month so assertions must not depend on month labels. Verify in the first run.
- D6 oncall: packages.oncall_sync.providers.get_oncall_sync_service is lru_cached; patch the module attribute where __init__._run_oncall_sync imports it lazily (inside the function, so patch packages.oncall_sync.providers, not the package). Verify at Step 6.
- D7 The pins hold with the default test environment (no network, no AWS credentials): confirmed by running each test file alone and the whole directory.
- D8 Makefile target check-package-shape exists in the working tree because this branch contains TASK-114.1 (4df8380c); the task branch is cut from main, so run it only if `grep check-package-shape app/Makefile` finds it there.

## Blast radius and rollback
Tests and one markdown file only; no production import, setting, plugin or infrastructure change. A wrong pin can only fail CI on this PR or later rebuild PRs (145.9, 88, 52/65, 124.1, 146.2), which would then have to update the one-line entry-point import and the edge fixture. `git revert` restores the previous state completely; no ordering constraints, no waits, no deploy. Domain-model evolution gate: not applicable (no entity or model is introduced or changed; the stale-channel pin deliberately does not touch incident records).

## Size estimate and gate
Production: 0 files, 0 LOC. Docs: 1 file (INVENTORY.md, about 10 changed lines). Tests: 5 new files plus conftest additions, about 900 LOC (stale ~200, identity center ~230 with fakes, spending ~190, access ~90, oncall ~140, conftest ~60). Total touched ~7 files, 1 subsystem (tests). The CLAUDE.md gate (production LOC > 400, > 10 files, two subsystems, refactor mixed with behaviour, non-revertable) is NOT tripped. Review load is the risk (about 900 test LOC, two fake sets). Mitigation: commit order stale -> identity center/spending -> access/oncall so a split falls out cleanly if the reviewer asks (open question 1).

## Verification gate (from /workspace/app, in this order)
1. During work: `uv run ruff check .` and the targeted files, e.g. `uv run pytest tests/integration/legacy_surface -q`.
2. At the end, once each and sequentially: `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` then `uv run pytest tests --ignore=tests/smoke`.
3. `make check-import-contracts`, `make check-settings-key-ownership`, and `make check-package-shape` only if present on main when the branch is cut. If a fake lands under tests/factories also `make check-fake-coverage` (the plan keeps fakes inside legacy_surface, so not expected).
Report each command with its actual output. No smoke tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Files (all under app/tests/integration/legacy_surface/): conftest.py (+55 additive: ChannelAwareSlackClient, RoutedSlackEdges, routed_slack_client fixture); new test_incident_stale_channel_job_run.py (11 tests), test_aws_identity_center_provision_job_run.py (11), test_aws_spending_data_update_job_run.py (12), test_access_sync_reconciliation_job_run.py (4), test_oncall_sync_job_run.py (8); INVENTORY.md five scheduled-job rows (Defined-at, rebuild tickets, oncall Target 'per TASK-146 re-cut', Pinned-by) plus a note on incident_legacy_upgrade. No production code changes; Tier-2 lease wrapper bypassed by design. Each file mutation-checked once (inverted expected value fails, reverted). Gates: ruff clean; mypy 41 errors (baseline, none in touched files); pytest tests --ignore=tests/smoke 6437 passed; make check-import-contracts (13 kept, 0 broken), check-settings-key-ownership OK, check-package-shape OK.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-06T12:42:00Z

---

AC proposal (no removal): AC #3 only says 'marks each job row pinned'; new AC #5 also requires the stale refs fixed (the five Defined-at lines are stale, the stale-channel row points to TASK-38 instead of TASK-145.9, the oncall row points to archived TASK-124.2/TASK-123 instead of TASK-146.2). AC #4 wording 'no new errors in touched files' is fine as is; the repo mypy baseline has pre-existing errors.

---

created: 2026-11-06T17:14:00Z

---

2026-11-06 plan approved (human). OQ1: one PR. OQ2: access sync pinned with a recording fake coordinator at get_access_sync_coordinator (option A). OQ3: identity-center and oncall faked at the adapter-builder and provider seams. OQ4: oncall Target cell reads 'per TASK-146 re-cut'.

---
<!-- COMMENTS:END -->
