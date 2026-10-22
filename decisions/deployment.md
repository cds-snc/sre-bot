---
status: Accepted
date: 2026-10-22
applies: now
scope: Image identity, ECR tag policy, task-definition ownership, rollback and its rehearsal on ECS.
---

# Deployment

## Context

Until TASK-111.16, production ran `sre-bot:latest`. The deploy workflow pushed `latest` and forced a new deployment of the same task-definition revision, and the service had no deployment circuit breaker, only the CPU and memory alarm rollback. A rollback would have relaunched the same revision, and so the same broken image. A deploy that failed boot hung while the old tasks kept serving, and recovery was a manual retag of the previous image as `latest`. [configuration.md](configuration.md) and [lifecycle.md](lifecycle.md) rely on a rollback that runs the previous image.

`tf_apply.yml` runs on a push to `main` that changes `terraform/`. `build_and_deploy.yml` runs on any other push to `main`, and on demand.

## Decision

**Image identity.** Every build is tagged `<git sha>-<YYYY-MM-DD>`, computed once per run. ECR rejects overwriting that tag, so a rerun on the same commit and day reuses the pushed image and builds nothing. `latest` is a movable pointer that ECR exempts from immutability. It moves only when a new image is pushed and is never a deploy reference ([AWS ECS image best practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/application.html)).

**Pinned revisions.** Each deploy registers a task-definition revision whose image is `<repository>@sha256:<digest>`, resolved from ECR for that tag. The tag and digest go to the run summary. A revision therefore always runs the image it was deployed with, whatever happens to tags later.

**Ownership.** Terraform owns the cluster, the service, the task-definition family and every attribute of them except which revision the service runs (`ignore_changes = [task_definition]`). `track_latest` stays false, so the workflow's revisions are not drift, and `skip_destroy` keeps every revision ACTIVE, since an INACTIVE revision cannot be a rollback target. The deploy workflow owns the running revision. It renders from the family's latest revision, changes only the image, registers it and deploys it. A terraform change to the task definition (environment, secrets, CPU, memory, the container template) therefore reaches production at the next deploy. After such an apply, run the deploy workflow for the current image. IAM policies and every other resource apply at `tf apply`.

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

## Checks

- `terraform/ecs.tf`: `aws_ecs_service.main` has `deployment_circuit_breaker` with `rollback = true`, `health_check_grace_period_seconds`, and `ignore_changes = [task_definition]`; `aws_ecs_task_definition.sre-bot` has `skip_destroy = true` and no `track_latest = true`.
- `terraform/ecr.tf` sets `IMMUTABLE_WITH_EXCLUSION` with `latest` as the only exclusion filter.
- `build_and_deploy.yml` registers an image referenced by `@sha256:` and runs `verify-ecs-deployment.sh` after the wait. Its deploy job is in group `ecs-deploy`, and `tf_apply.yml` is in group `terraform-apply`.
- No workflow deploys or SBOM-scans `:latest`.
- The build and deploy jobs of `build_and_deploy.yml` run `require-admin.sh` for manual runs and re-runs.

**Changes:**
- 2026-10-22: new record: digest-pinned revisions registered by the deploy workflow, the circuit breaker with rollback, serialized deploys, manual rollback and its rehearsal (TASK-111.16).
- 2026-10-22: the rehearsal runs through the deploy workflow's `rehearse_rollback` input and deregisters its revision (TASK-111.16).
- 2026-10-22: only repository admins may run or re-run the deploy workflow manually (TASK-111.16).
- 2026-10-22: the rehearsal always deregisters its revision and may run in working hours with notice (TASK-111.16).
