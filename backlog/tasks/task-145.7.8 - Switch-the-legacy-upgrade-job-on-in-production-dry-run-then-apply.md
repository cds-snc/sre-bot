---
id: TASK-145.7.8
title: 'Switch the legacy upgrade job on in production: dry run, then apply'
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-17T23:52:00Z'
labels:
  - incident
  - config
dependencies:
  - TASK-145.7.4
  - TASK-145.8.3
  - TASK-145.8.4
  - TASK-145.8.5
  - TASK-145.8.6
references:
  - decisions/incident-management.md
  - app/features/incident/README.md
parent_task_id: TASK-145.7
priority: medium
type: chore
ordinal: 512000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L8. After the TASK-145.8 cutovers have deployed: one config PR sets [incident_response] upgrade_mode = "dry_run" in production.toml; the human reads the report (blockers listed per Migration rule 7, already_upgraded expected 0); a second PR sets "apply"; the human records the applied report. Then mode back to off or kept for the rerun per the README.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dry-run and apply reports are recorded in the notes with zero blockers left (checks the production part of parent AC #13)
- [x] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN, dry-run half (awaiting human approval). Doc-11 row 18.L8; branch task-145.7.8-job-dry-run from main e5b57b29. Human reorder 2026-11-17: the dry run goes ahead of 18.L7c; the apply is a second PR after L6a (145.8.3) and L7a.3 (145.8.5.3) are deployed and soaked and a dry run has zero blockers. The TASK-145.7.12 plan stays out of this PR.

Facts (main e5b57b29)
- Production runs the job unregistered: upgrade_mode = "off" in app/config/base.toml:225; production.toml's [incident_response] (:30-34) sets only Slack ids. [scheduler] enabled = true in production.toml:11.
- What a dry run does every upgrade_interval_minutes (30), on one replica under the scheduler:incident_legacy_upgrade lease (900 s):
  - one whole-table Scan of the incidents table with ConsistentRead, capped by [incident_core] full_read_max_items = 10000 (base.toml:207);
  - one Slack auth.test through the TenantVerifier;
  - one incident_legacy_upgrade_report event; nothing is written;
  - each optional legacy field the bridge cannot map logs incident_legacy_field_dropped as a warning (legacy_items.py:88).
- Access is already granted: the task role allows Scan on local.dynamodb_table_arns (terraform/iam.tf:34-47, dynamodb.tf:302), which includes incidents, bindings and idempotency. The Tier-2 lease store is the one legacy leased jobs already use (jobs/scheduled_tasks.py:127-133).
- Read cost: incidents is provisioned at read_capacity = 2 (dynamodb.tf:91-95). No production path scans it today (list_incidents is only called by the dev command, modules/dev/incident.py:20). TASK-145.5.7.3 OQ17 sized one consistent read at ~40-80 RCU for 323 items. At 2 RCU/s an interval replenishes 3600 RCU, so a run uses about 2% of it, and the burst reserve absorbs the spike.
- The ECS deployment alarms that roll a deploy back are CPU and memory only (terraform/ecs.tf:73-77). A blocked dry run's error logs cannot roll back a deploy.
- The alarms post to the SNS warning topic when errors reach 1 per minute or warnings reach 10 per minute (terraform/alarms.tf, variables.tf:16-26).

Changes
1. app/config/production.toml [incident_response]: upgrade_mode = "dry_run". The interval and lease stay at their base values (OQ5).
2. TDD, app/tests/unit/features/incident/response/test_incident_response_settings_load.py:
   - test_no_environment_file_switches_the_upgrade_job_on is narrowed to ci and local (still off);
   - a new test, production_runs_the_upgrade_job_as_a_dry_run, asserts production resolves dry_run with interval 30 and lease 900 and never apply;
   - the module docstring is updated to match.
   Failing test first, then the config line.
3. features/incident/README.md run procedure:
   - "When" is reworded: a dry run may start once L2b is deployed (it writes nothing); the first apply follows the last TASK-145.8 reader cutovers (L6a and L7a.3) deployed and soaked; TASK-145.7.12's roles step maps roles in a later rerun.
   - "Dry run first" gains the exact read command below and the alarm note (OQ4).
4. TASK-145.7.8 (this task): dependency and comment already edited; the notes get the dry-run report after deploy (human). AC #1 checks only once the apply report is recorded too.

Size: 1 config line, 1 test file, 1 README section. One subsystem (configuration). The merge deploys a read-only job.

Blast radius and rollback
Reads only. The cost is one consistent Scan of incidents every 30 minutes plus one auth.test. Rollback: a PR setting the mode back to off (or git revert), shipped by the deploy workflow; never a console change.

Human steps
- Before merge (read-only):
  aws dynamodb describe-table --table-name incidents --region ca-central-1 --query 'Table.{items:ItemCount,bytes:TableSizeBytes,rcu:ProvisionedThroughput.ReadCapacityUnits,billing:BillingModeSummary.BillingMode}'
  Optional: refreshes TASK-145.5.7.3 OQ17's sizing (323 items on 2026-11-04). Expect items well under 10000.
- After the deploy, plus about 30 minutes:
  aws logs filter-log-events --region ca-central-1 --log-group-name /ecs/sre-bot-app --filter-pattern '"incident_legacy_upgrade_report"' --start-time $(( ($(date +%s) - 7200) * 1000 )) --query 'events[].message' --output text
  Record the report in TASK-145.7.8's notes: mode dry_run; tenant_check verified (D10); scanned; already_upgraded (expected to be the items upgraded on write since #1859, not 0 as the description said); to_upgrade; and the blockers (unbound, unmatched_status, unreadable) by id. Blockers: fix by hand in the table (README "A blocked dry run"), or PR the mode to off first if the error alarm repeats.

Open questions, reassessed at program scope (2026-11-17, human asked: ADRs, doc-11, doc-15, doc-16, prior and upcoming tasks, cited practice). Settled by earlier decisions: former OQ2, OQ3 and OQ5. Open: OQ1 (a doc fix) and OQ4 (a small gap).

Settled, no question:
- Running while in dry_run (former OQ2): TASK-145.5.7.3 OQ18, human 2026-11-04. The job runs every interval while the mode is dry_run or apply; a blocked dry run is switched off by PR while items are fixed; the procedure ends with off after a clean apply. Migration rule 6 expects reruns. Keeping dry_run on until the apply PR follows it.
- Read cost (former OQ3): cloud-portability.md:27 and :55 (TASK-27.5): read_all is a strongly consistent whole-table read for batch jobs, capped by the caller's setting. TASK-145.5.7.3 OQ17 sized it on this table. No ADR rules DynamoDB capacity mode, and none is needed at about 2% of an interval's capacity. The describe-table check is optional. (Correction: the earlier pointer to TASK-108/109 was wrong; both are Done and are not about capacity.)
- Interval and first-run timing (former OQ5): D5 (TASK-145.5.7, interval 30), TASK-145.5.7.3 OQ17 (lease 900 s) and OQ19 (first run one interval after boot, stated in the README; TASK-64 makes it explicit). Unchanged.
- Blocked-run alarm: TASK-145.5.7.3 OQ15 and OQ20: a blocked dry run is a failed run logged once at error, so the error alarm fires every run until the mode goes off. ADR-backed (observability.md:16, ERROR is failed work; reliability.md safe_run).
- D10: TASK-157's smoke settled the inbound shape (TASK-145.5.7, 2026-11-04). The first dry run's tenant_check confirms the auth.test side. Already in the run procedure.
- doc-15 has nothing on the upgrade job (its "dry run" rows are the CVE/VDP exercises). doc-16 L8 matches the reorder.

OQ1 A dry run before the last cutovers deploy: doc conflict, fix in this PR.
- ADR: incident-management.md Migration rule 3 ("runs per environment, dry run first") puts no order on the cutovers for a dry run. Rule 1's "readers before writers" is about writes, and a dry run writes nothing.
- Conflict: the README's "When" bullet (TASK-145.5.7.3) puts the first run after TASK-145.8's deploy.
- Prior: this task's 2026-11-10 notes ("dry_run ... safe once L2b is deployed"); the human reorder of 2026-11-17.
- Upcoming: none changes it. TASK-145.7.12 adds roles counts to later runs.
- Recommended: reword the README "When" bullet (Changes item 3). No ADR edit.

OQ4 Per-item drop warnings in a batch run: a small gap, conditional fix.
- ADR:
  - incident-management.md Migration rule 3 ("each run emits one structured report with its counts") and rule 7 (a dropped value is counted in the run's report with the record and field);
  - observability.md:16 (WARNING means degraded-but-handled) and :28 (alerting keys on structured fields; TASK-94 moves the filters there).
- Prior: TASK-145.5.8 and D7 (TASK-145.5.7): the shared bridge logs incident_legacy_field_dropped per drop, made for the read path. The runner already reports every drop in the report's dropped list (id, field), so in a batch run each drop appears twice: the report plus one warning per drop per run.
- Gap: no rule says whether a batch run's per-item conditions go only into its report. With 10 or more drops in one run, the warning alarm (10 per minute, terraform/alarms.tf; SNS warning topic, not the deploy rollback) fires every 30 minutes for a condition that is already known and recorded.
- Practice: every alert should be actionable, and a known, recorded condition that recurs on schedule is noise (Google SRE, Monitoring Distributed Systems: https://sre.google/sre-book/monitoring-distributed-systems/). A batch job aggregates per-item outcomes into its run summary rather than one log line per item (the job's own rule 3).
- Upcoming: TASK-94 AC #2 decides how expected-volume warnings are handled (filter by $.event, downgrade, or keep). TASK-145.7.12 already touches the runner and the drop reporting.
- Recommended:
  (a) Nothing changes in this PR. The first report shows the real drop count.
  (b) If one run drops 10 or more fields, TASK-145.7.12 (merged after the apply, before the rerun) gives the runner a silent drop sink: in a batch run the bridge's drops go only into the report, and the read path still logs them. It also adds an incident-management.md rule 3 clause: "a batch run reports per-item outcomes in its report, not one log event per item".
  (c) TASK-94 gets a comment listing incident_legacy_field_dropped (batch) and incident_legacy_upgrade_report at error (blocked run) as expected-volume candidates for AC #2.
  Until (b) lands, a noisy dry run is switched off by PR (OQ18's procedure).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (human question, answered from the program plan): when the job may run.
- dry_run writes nothing: safe in any environment once L2b (TASK-145.7.4, #1844) is deployed; running it earlier than this task's config PR only surfaces blockers sooner.
- apply waits on: L2b deployed (before it the job raises items to version 1 without a binding); L5r (TASK-145.8.2) rollback guard deployed; L6a-L7b (TASK-145.8.3-145.8.6) deployed and soaked (TASK-145.7 OQ18: the legacy Incident model, extra=forbid, cannot read an upgraded item, so a reader cutover reverted after apply breaks; after apply a regression is fixed forward).
- No need to wait for the whole stack: the stored shape is versioned (record_version); a later shape change bumps the version with its own upgrade step while readers accept both; the job reruns after TASK-145.12.2 anyway (README Rerun rule), and the rebuilt writers upgrade each item they touch from L3/L6a on regardless of the job.
- The L5 re-plan (TASK-145.7.7 R4-R6, 2026-11-10) does not change what the job writes: legacy items always have a channel, so they keep the conversation copy, one primary chat binding and record_version 2.

2026-11-17: dry-run half plan APPROVED by the human as recommended after the program-scope reassessment (OQ1 README When-bullet fix in this PR; OQ4 no code change here, conditional drop sink in TASK-145.7.12 if a run drops 10 or more, TASK-94 comment).

2026-11-17: dry-run half implemented (TDD) on task-145.7.8-job-dry-run from main e5b57b29.
- app/config/production.toml: [incident_response] upgrade_mode = "dry_run" (interval 30 and lease 900 from base).
- app/tests/unit/features/incident/response/test_incident_response_settings_load.py: the "no environment file switches the job on" test narrowed to ci and local; new test_production_runs_the_upgrade_job_as_a_dry_run (real production loader: dry_run, 30, 900). It failed first (1 failed, 22 passed), then passed.
- app/features/incident/README.md run procedure: "When" reworded (OQ1: dry run once the binding step is deployed; apply after 145.8.3 and 145.8.5.3 deployed and soaked plus a zero-blocker dry run; 145.7.12 maps the roles in a later rerun). "Dry run first" gains: already_upgraded is not 0 in production (upgrade on write), the read command, the mode stays dry_run until the apply PR, and the drop-warning alarm note (OQ4).
- OQ4 follow-ups: TASK-94 comment (expected-volume candidates); TASK-145.7.12 note (conditional silent drop sink plus Migration rule 3 clause if a run drops 10 or more).
Gates (from app/):
- ruff check: All checks passed.
- make check-import-contracts: 14 kept, 0 broken.
- check-settings-key-ownership: OK.
- check-package-shape: OK, 3 baselined.
- check-test-seams: OK, 47/12 baselined.
- mypy: Found 40 errors in 13 files, the main baseline, all in legacy modules; the touched test file has no issues.
- pytest tests --ignore=tests/smoke: 7624 passed.
- Targeted: settings load and job registration tests, 30 passed; the configuration-file suites, 167 passed.
AC #2 checked. AC #1 stays open: the dry-run report (human, after deploy) and the apply report (second PR) go into these notes.
Human after merge and deploy: read incident_legacy_upgrade_report about 30 min after the task starts (README command) and record it here: tenant_check, scanned, already_upgraded, to_upgrade, dropped count, blockers by id. Blocked or noisy (10 or more drops a run): a PR sets the mode to off while items are fixed.

2026-11-17: first production dry-run report (human ran the README command; image 203aeea1, 23:30:04Z):
mode dry_run, outcome succeeded, failures [], cap 10000, scanned 336, already_upgraded 1, to_upgrade 335, pending 335, binding_skipped 0, unbound [], unmatched_status [], unreadable [], dropped [], tenant_check verified (tenant T2G2S06PM).
Reading:
- Zero blockers: the apply's dry-run gate is met.
- D10 confirmed: the auth.test org-token shape verifies under the team_id-only [slack.tenant].
- Every item has a conversation (binding_skipped 0, unbound empty).
- No drops, so TASK-145.7.12's conditional drop sink (OQ4) is not needed.
- already_upgraded 1: one legacy item upgraded on write since #1859.
Finding: the same report was logged twice per interval, by two replicas (instance 6c30fec7 at 23:30:04.497Z, 5636151a at 23:30:05.196Z). run_if_leased releases the lease when the job ends (infrastructure/coordination/lease.py:14-17), so a run shorter than the replicas' tick offset (about 1 s here) runs again on the other replica. Harmless here: a dry run writes nothing, and an apply run is guarded on record_version, so a second run counts the items as already_upgraded. It doubles the scan (still about 4% of an interval's read capacity) and gives two reports per interval. ADR gap raised with the human (reliability.md lease semantics, TASK-64 scope).
AC #1 stays open until the apply report. The apply now waits only on 145.8.3 (L6a) and 145.8.5.3 (L7a.3) deployed and soaked.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T19:34:00Z

---

2026-11-16 (human, TASK-145.8.5 OQ7): the apply waits on TASK-145.7.12 (the job maps the report's Drive roles into the record); the dry run reports roles mapped and dropped.

---

created: 2026-11-17T22:13:00Z

---

2026-11-17 (human, TASK-145.7.12 session): sequencing changed. (1) The dry-run config PR goes next, before TASK-145.7.12 is implemented: upgrade_mode = "dry_run" in app/config/production.toml. A dry run writes nothing: one capped whole-table read and the Slack tenant check (it confirms D10's auth.test shape). Any blocker (unbound, unmatched_status, unreadable) is fixed by hand while L6a and L7a.3 merge. A blocked run logs at error every 30 min, so set the mode back to off while fixing. (2) The apply waits only on TASK-145.8.3 (L6a) and TASK-145.8.5.3 (L7a.3) deployed and soaked, plus a dry run with zero blockers. (3) The apply no longer waits on TASK-145.7.12: by its approved plan (OQ1/OQ2) the roles step fills roleless items at version 2 too, so items raised by this apply get their roles when 145.7.12 runs, and read_incident_roles covers them until then. TASK-145.7.12 merges after the apply and runs in the rerun (dry_run, then apply), before TASK-145.13. Dependency on TASK-145.7.12 removed. The 145.7.12 roles counts appear only in runs after it merges.

---
<!-- COMMENTS:END -->
