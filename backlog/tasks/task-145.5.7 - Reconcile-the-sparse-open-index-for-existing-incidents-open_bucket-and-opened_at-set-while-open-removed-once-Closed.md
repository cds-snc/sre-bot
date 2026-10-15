---
id: TASK-145.5.7
title: >-
  Reconcile the sparse open index for existing incidents: open_bucket and
  opened_at set while open, removed once Closed
status: To Do
assignee: []
created_date: '2026-10-14 23:10'
updated_date: '2026-10-15 17:51'
labels:
  - incident
  - features
  - records
  - reliability
dependencies:
  - TASK-145.5.2
  - TASK-145.5.4
  - TASK-27.5
references:
  - decisions/reliability.md
  - decisions/lifecycle.md
  - 'https://12factor.net/admin-processes'
  - >-
    https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general-sparse-indexes.html
  - 'https://github.com/cds-snc/sre-bot/issues/1696'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 393000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 9 of Stack K (handoff doc-13). Legacy items carry no open_bucket or opened_at, so the sparse open index (TASK-145.5.1) is empty for them. The reconcile has to run after TASK-145.8 is deployed (before then, legacy writers create and close incidents without maintaining the attributes) and before TASK-145.9 merges (the stale-channel nudge is the first reader). by_channel needs nothing, because DynamoDB fills it from the existing channel_id.

TENTATIVE (human, 2026-10-14; the analysis is redone when this task is planned): option (c) below.

CONTEXT (verified 2026-10-14)
- No one-off has ever run in production: ECS Exec is not enabled (terraform/ecs.tf, no ssmmessages in terraform/iam.tf), nothing calls RunTask, and app/bin/entry.sh only starts uvicorn. Two replicas run.
- RecordStore has no full-table read until TASK-27.5. Scheduled jobs run only in production (app/server/lifespan.py:122-126). The idempotency record TTL is one hour, and decisions/reliability.md:22 says the IdempotencyStore is not a job-status store.
- Legacy created_at is an epoch-float string; opened_at is the fixed-width ISO-8601 UTC form of it. Scale is plausibly a few hundred items, to be confirmed (describe-table ItemCount, and the dry-run counts).

OPTIONS
(a) An app/bin script run by a human via ECS Exec into a serving task. Pros: simple code. Cons: needs enable_execute_command, ssmmessages IAM, the Session Manager plugin and session logging first; interactive and hard to audit; runs inside a serving replica. Rejected.
(b) The same command as a one-off ECS RunTask from a workflow_dispatch workflow (same image and task role). Pros: the 12-factor admin-process model (https://12factor.net/admin-processes); auditable; maps to a Kubernetes or OpenShift Job. Cons: a new OIDC role with ecs:RunTask and iam:PassRole, network configuration, an entrypoint override, a new workflow; a new ops pattern for two small backfills. The right answer if one-offs become routine, with an ADR on admin processes. References: https://wiki.simpler.grants.gov/product/decisions/infra/0007-database-migration-architecture, https://github.com/researchsquare/run-ecs-task-action.
(c) An in-app reconcile job: the incident plugin registers a leased Tier-2 job, reached through the ServiceScopeOpener (TASK-145.5.2); OPEN_INDEX_RECONCILE_MODE off (default, not registered), dry_run or apply; every write is a guarded RecordStore.update (set when not Closed and open_bucket absent; remove when Closed), so a concurrent close wins and reruns are no-ops; no done-marker; writes paced for the provisioned capacity; one structured report event per run (scanned, to_set, to_remove, already_ok, skipped, guard_lost, pending). Run: after TASK-145.8 deploys, set dry_run and redeploy, then apply and redeploy, then off once a run reports pending=0. TASK-145.9 deletes it. Pros: existing machinery, no new infra or prod access, portable. Cons: a mode change is an SSM edit plus a redeploy; only production runs jobs, so the rehearsal is the prod dry run; the code sits briefly in the runtime. TASK-145.12 can reuse the pattern.
(d) Lazy reconcile on read or write. Rejected: a sparse index cannot surface items that never got the attribute, which are exactly the quiet incidents the nudge must find.
(e) A permanent periodic reconcile beside the nudge. Rejected unless writers can drift: it keeps a full scan the index exists to avoid, and TASK-145.8 sets and removes both attributes in one atomic update.
(f) An app/bin Python script run from a workstation with production credentials (precedent: app/bin/unlock-sync-job.sh). Pros: zero infra; CloudTrail records the caller. Cons: production write credentials on a workstation, configuration outside the release, a human must hit the TASK-145.8 to TASK-145.9 window. Runner-up.
Further references: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.OnlineOps.html, https://aws.amazon.com/blogs/database/evolve-your-amazon-dynamodb-tables-data-model, https://railsatscale.com/2023-01-04-how-we-scaled-maintenance-tasks-to-shopify-s-core-monolith/article.html, https://www.martinfowler.com/bliki/ParallelChange.html.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The runner choice is re-assessed against the options above and recorded in the plan
- [ ] #2 The reconcile ships switched off and, when run, leaves every incident not Closed with open_bucket OPEN and opened_at and every Closed incident with neither (tested against InMemoryRecordStore, dry run writing nothing)
- [ ] #3 Reruns change nothing, a concurrent close or reopen wins over the reconcile, and items with an unparseable status or created_at are skipped and counted
- [ ] #4 The run procedure (dry run then apply, per environment, after TASK-145.8 is deployed) and the removal owner are recorded; running it is a precondition of TASK-145.9, not of this task
<!-- AC:END -->
