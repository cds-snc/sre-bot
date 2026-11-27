---
status: Accepted
date: 2026-10-22
applies: now
scope: Image identity, ECR tag policy, task-definition ownership, rollback and its rehearsal on ECS, and how DynamoDB tables are provisioned, protected, backed up and removed.
---

# Deployment

## Context

Until TASK-111.16, production ran `sre-bot:latest`. The deploy workflow pushed `latest` and forced a new deployment of the same task-definition revision, and the service had no deployment circuit breaker, only the CPU and memory alarm rollback. A rollback would have relaunched the same revision, and so the same broken image. A deploy that failed boot hung while the old tasks kept serving, and recovery was a manual retag of the previous image as `latest`. [configuration.md](configuration.md) and [lifecycle.md](lifecycle.md) rely on a rollback that runs the previous image.

`tf_apply.yml` runs on a push to `main` that changes `terraform/`. `build_and_deploy.yml` runs on any other push to `main`, and on demand.

## Decision

**Image identity.** Every build is tagged `<git sha>-<YYYY-MM-DD>`, computed once per run. ECR rejects overwriting that tag, so a rerun on the same commit and day reuses the pushed image and builds nothing. `latest` is a movable pointer that ECR exempts from immutability. It moves only when a new image is pushed and is never a deploy reference ([AWS ECS image best practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/application.html)).

**Pinned revisions.** Each deploy registers a task-definition revision whose image is `<repository>@sha256:<digest>`, resolved from ECR for that tag. The tag and digest go to the run summary. A revision therefore always runs the image it was deployed with, whatever happens to tags later.

**Ownership.** Terraform owns the cluster, the service, the task-definition family and every attribute of them except which revision the service runs (`ignore_changes = [task_definition]`). `track_latest` stays false, so the workflow's revisions are not drift, and `skip_destroy` keeps every revision ACTIVE, since an INACTIVE revision cannot be a rollback target. The deploy workflow owns the running revision. It renders from the family's latest revision, changes only the image, registers it and deploys it. A terraform change to the task definition (environment, secrets, CPU, memory, the container template) therefore reaches production at the next deploy. After such an apply, run the deploy workflow for the current image. IAM policies and every other resource apply at `tf apply`.

**Secret parameters.** A secret or non-public value reaches the task as an SSM parameter named in `terraform/ssm.tf` (`sre_bot_secret_names`), created with a write-only placeholder and set by a human with `put-parameter` after the apply. A new name lands in its own PR, before the code that reads it, and the human sets the value before that consumer merges, so no running code reads the placeholder. A revert never removes a name: `prevent_destroy` does not survive a removed resource block, and a destroyed parameter loses the human-set value, which terraform cannot restore. Removing a name goes through the retired-names map (`audit_env_names.py`) and a `removed` block with `lifecycle { destroy = false }`, then a manual delete once nothing reads it ([Terraform removed block](https://developer.hashicorp.com/terraform/language/block/removed), [resource lifecycle](https://developer.hashicorp.com/terraform/language/resources/syntax)).

**Tables.** Every DynamoDB table in `terraform/dynamodb.tf` follows one rule set.
- *Capacity.* A table is on-demand (`PAY_PER_REQUEST`), capped by `on_demand_throughput` at the `dynamodb_max_read_request_units` and `dynamodb_max_write_request_units` variables (default 1000 each). On-demand is AWS's "default and recommended throughput option for most DynamoDB workloads" ([throughput capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html)). Provisioned tables at one or two units throttled a production batch (the incident legacy upgrade, 2026-11-26), and they would throttle every backfill. The ceiling is a cost bound against unbounded traffic ([OWASP API4:2023](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/), [maximum throughput](https://aws.amazon.com/blogs/database/introducing-configurable-maximum-throughput-for-amazon-dynamodb-on-demand/)). Past it, requests throttle, and the app treats throttling as a transient error, never as data loss. The ceiling values are variables with defaults, so a deployment changes them in its own inputs ([configuration.md](configuration.md): no plain constants). An existing provisioned table moves to on-demand in the next task that changes it. Switching is online and can be reversed.
- *Protection.* A new table sets `deletion_protection_enabled = true` and point-in-time recovery, as AWS Security Hub controls DynamoDB.6 and DynamoDB.2 expect ([DynamoDB controls](https://docs.aws.amazon.com/securityhub/latest/userguide/dynamodb-controls.html)). The recovery window is at most the data's retention (1 to 35 days; the price does not depend on it: [PITR](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html)).
- *Backups and retention.* Every table's ARN goes in `local.dynamodb_table_arns`, which feeds both the task role's table statement and the AWS Backup selection, so a new table cannot be missed in either. A table whose items expire sooner than the 30-day backup retention, such as the webhook inbox (7-day item TTL), is listed in `local.dynamodb_backup_excluded_arns` with the reason in a comment, and the selection takes `setsubtract` of the two lists. AWS Backup rejects an ARN that one selection both includes and excludes; `not_resources` only narrows a wildcard or tag selection ([selection by resource](https://docs.aws.amazon.com/aws-backup/latest/devguide/assigning-resources.html)). Its point-in-time recovery window equals that TTL, so no copy outlives the data's retention ([OWASP ASVS 4.0.3 8.3.8](https://owasp-aasvs4.readthedocs.io/en/latest/8.3.8.html): retention classification with automatic deletion). Changing the selection's resources replaces the selection, not the recovery points, which stay in the vault.
- *Removal.* A revert never destroys a table: with deletion protection on, such an apply fails. A table is removed by a PR that takes its ARN out of the list and adds a `removed` block with `lifecycle { destroy = false }`, as for a secret name above. Once nothing reads the table, a human turns off its deletion protection and deletes it, after the retention question for its data and its recovery points is settled (TASK-91 is the precedent).

**Circuit breaker.** `aws_ecs_service.main` enables the deployment circuit breaker with rollback, at AWS defaults. The breaker counts tasks that fail to reach RUNNING, and tasks replaced because a load balancer or container health check failed. At two replicas it trips after three consecutive failures and rolls back to the last COMPLETED deployment ([ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)). The AWS provider exposes only `enable` and `rollback`, so the threshold settings AWS added in 2026 cannot be set yet. Revisit this when the provider supports them. The CPU and memory alarm rollback stays. The health-check grace period exceeds boot time ([health-checks.md](health-checks.md)), so a slow but healthy boot is not counted as a failure.

**A deploy succeeds only on its own revision.** The services-stable waiter also succeeds after a rollback, because the service settles on the old revision. The workflow therefore fails, and says it rolled back, unless the service runs the revision this run registered and the PRIMARY deployment is COMPLETED.

**Serialization.** The deploy job runs in concurrency group `ecs-deploy` with `queue: max`, so deploys and rollbacks run one at a time in arrival order and none is dropped. `tf_apply` has its own group, `terraform-apply`. The two share no group: they write disjoint things, and a shared group would serialize them without ordering them.

**Manual rollback.** For a deploy that boots but misbehaves, run the deploy workflow with an existing image tag. Only repository admins may run the workflow manually or re-run it, since either one chooses what production runs; the build and deploy jobs check the role of the actor who triggered the run, on every attempt. Merge deploys stay gated by the `main` ruleset's review. The tag is validated against the format, resolved to its digest in ECR, and no build runs. A rollback leaves `main` unchanged, so the next merge deploys forward again: revert or fix forward first. When the workflow is unavailable, point the service at an earlier revision with the AWS CLI. Procedure: [docs/runbooks/roll-back-a-deployment.md](../docs/runbooks/roll-back-a-deployment.md).

**Retention.** The ECR repository expires nothing. A future lifecycle policy counts images rather than ageing them, and keeps every image an ACTIVE revision references.

**Rehearsal.** Rollback is rehearsed once in production before the first deploy that depends on it, and again whenever this mechanism changes (service deployment settings, grace period, the verify step). Like every production change it runs through the deploy workflow: the `rehearse_rollback` input deploys the running image with an invalid `ENVIRONMENT`, a deploy-coupled defect, and the run always deregisters that revision, even when cancelled, so the next deploy does not render from it. The old tasks keep serving throughout, so it can run in working hours with notice. The rehearsal checks that the old tasks keep serving, the breaker fails the deployment and returns to the previous revision, and the workflow fails and notifies. The date and the measured time to roll back go in the runbook ([AWS REL12-BP05](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_testing_resiliency_game_days_resiliency.html)).

## Consequences

- A terraform task-definition change waits for the next deploy, and the runbook carries the redeploy step.
- Each deploy adds a revision to the family, and none is deregistered.
- The task definition shows a digest, not a tag. The run summary maps one to the other.
- Signing and build provenance are not decided here; they key on the digest this record pins.
- `latest` remains for the render base and manual scans. Dropping it, and moving to plain `IMMUTABLE`, is a follow-up.
- Tolerated until each table's next task (or a task that moves them all, proposed to Lane A on 2026-11-27): the tables other than `webhooks` and `sre_bot_webhook_inbox` are provisioned and have neither deletion protection nor point-in-time recovery.
- No record sets a general data-retention policy. Retention is decided per store, by its TTL and its backup rule; a retention record is a gap to fill when a second store needs one.

## Checks

- `terraform/ecs.tf`: `aws_ecs_service.main` has `deployment_circuit_breaker` with `rollback = true`, `health_check_grace_period_seconds`, and `ignore_changes = [task_definition]`; `aws_ecs_task_definition.sre-bot` has `skip_destroy = true` and no `track_latest = true`.
- A PR that removes a name from `sre_bot_secret_names` in `terraform/ssm.tf` carries a `removed` block with `destroy = false` and the name in the retired-names map.
- Review (`terraform/dynamodb.tf`): a new or changed table is `PAY_PER_REQUEST` with `on_demand_throughput` from the two ceiling variables; a new table has `deletion_protection_enabled = true` and `point_in_time_recovery`; every table's ARN is in `local.dynamodb_table_arns`, and each `local.dynamodb_backup_excluded_arns` entry states its reason, with the selection taking the difference of the two lists, never a `not_resources` of a listed ARN; a PR that removes a table carries a `removed` block with `destroy = false`.
- `terraform/ecr.tf` sets `IMMUTABLE_WITH_EXCLUSION` with `latest` as the only exclusion filter.
- `build_and_deploy.yml` registers an image referenced by `@sha256:` and runs `verify-ecs-deployment.sh` after the wait. Its deploy job is in group `ecs-deploy`, and `tf_apply.yml` is in group `terraform-apply`.
- No workflow deploys or SBOM-scans `:latest`.
- The build and deploy jobs of `build_and_deploy.yml` run `require-admin.sh` for manual runs and re-runs.

**Changes:**
- 2026-10-22: new record: digest-pinned revisions registered by the deploy workflow, the circuit breaker with rollback, serialized deploys, manual rollback and its rehearsal (TASK-111.16).
- 2026-10-22: the rehearsal runs through the deploy workflow's `rehearse_rollback` input and deregisters its revision (TASK-111.16).
- 2026-10-22: only repository admins may run or re-run the deploy workflow manually (TASK-111.16).
- 2026-10-22: the rehearsal always deregisters its revision and may run in working hours with notice (TASK-111.16).
- 2026-11-27: Tables. DynamoDB tables are on-demand under ceiling variables and move from provisioned in the task that changes them; a new table has deletion protection and point-in-time recovery no longer than its data's retention; a table whose items expire before the backup retention is excluded from AWS Backup with its reason; a revert never destroys a table, and removal is a `removed` block with `destroy = false`. This supersedes the TASK-145.7.1 rollback, in which terraform destroyed an empty table (TASK-37.2.4, human).
- 2026-11-27: a backup exclusion is `local.dynamodb_backup_excluded_arns`, subtracted from the table list, not `not_resources`: the first apply failed with "both included and excluded from selection" after the old selection was destroyed, which left no table selected until the fix applied (TASK-37.2.4).
