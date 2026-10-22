---
title: Roll back a deployment
owner: SRE team (sre-bot maintainers)
last_reviewed: 2026-10-22
decisions:
  - decisions/deployment.md
---

# Roll back a deployment

Decision and rationale: [decisions/deployment.md](../../decisions/deployment.md).

Region `ca-central-1`, cluster `sre-bot-cluster`, service `sre-bot-service`, task-definition family `sre-bot-task`, log group `/ecs/sre-bot-app`, ECR repository `sre-bot`.

## When to use

- **A deploy failed to boot.** You need nothing: the circuit breaker already returned the service to the last completed revision, and the workflow failed with "Deployment rolled back". Fix forward or revert on `main`, then run [Verify](#verify).
- **A deploy boots but misbehaves** (errors, a broken command, a bad integration): roll back to the previous image ([Roll back to an earlier image](#roll-back-to-an-earlier-image)).
- **A bad terraform change to the task definition** (environment, secrets, CPU, memory) that the circuit breaker did not catch: roll back to the previous revision ([Roll back to an earlier revision](#roll-back-to-an-earlier-revision)). Rolling back the image keeps the bad task-definition change.
- **After a terraform change to the task definition**: it reaches production only at the next deploy. Redeploy the current image ([Redeploy the current image](#redeploy-the-current-image)).

## Permissions and tools

- GitHub: permission to run the **Build and Push to Container Registry** workflow (`build_and_deploy.yml`).
- AWS CLI fallback: a role with `ecs:DescribeServices`, `ecs:ListTaskDefinitions`, `ecs:DescribeTaskDefinition`, `ecs:UpdateService` and `ecr:DescribeImages` on the production account.

## Steps

### Find the image tags

Each run's summary lists the deployed tag (`<git sha>-<YYYY-MM-DD>`) and digest. To list the newest tags in ECR:

```bash
aws ecr describe-images --region ca-central-1 --repository-name sre-bot \
  --query 'sort_by(imageDetails,&imagePushedAt)[-5:].[imagePushedAt,imageTags,imageDigest]' --output table
```

### Roll back to an earlier image

1. GitHub, Actions, **Build and Push to Container Registry**, **Run workflow** on `main`, with `image_tag` set to the earlier tag.
2. The run checks the tag format, resolves the tag to its digest, builds nothing, and deploys a new revision that pins that digest. It fails if the service does not end on that revision.
3. `main` is unchanged, so the next merge deploys forward again. Revert or fix forward on `main` before that merge.

### Redeploy the current image

Run the workflow with `image_tag` set to the tag running now (the latest run summary, or [Find the image tags](#find-the-image-tags)). The new revision starts from the family's latest revision, so it carries the terraform change.

### Roll back to an earlier revision

Use this when the workflow is unavailable, or when the task definition itself is bad.

```bash
aws ecs list-task-definitions --region ca-central-1 --family-prefix sre-bot-task --sort DESC --max-items 5
aws ecs describe-task-definition --region ca-central-1 --task-definition sre-bot-task:<revision> \
  --query 'taskDefinition.containerDefinitions[0].image'
aws ecs update-service --region ca-central-1 --cluster sre-bot-cluster --service sre-bot-service \
  --task-definition sre-bot-task:<revision>
aws ecs wait services-stable --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service
```

The next workflow deploy renders from the latest revision again, so fix the terraform change before it.

## Verify

Run after every deploy or rollback.

1. The workflow posted its Slack success message, and the run summary shows the expected tag and digest.
2. One PRIMARY deployment, COMPLETED, running the expected revision:

   ```bash
   aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service \
     --query 'services[0].deployments[].[status,rolloutState,runningCount,desiredCount,taskDefinition]' --output table
   ```

3. No boot failure in the logs since the new tasks started:

   ```bash
   aws logs filter-log-events --region ca-central-1 --log-group-name /ecs/sre-bot-app \
     --start-time $(( ($(date +%s) - 1200) * 1000 )) \
     --filter-pattern '?plugin_boot_failed ?Traceback ?AttributeError ?credential_check_failed' \
     --query 'events[].[timestamp,message]' --output text | head -50
   ```

4. One Slack command in the test channel responds.
5. Run the change-specific checks in the task's notes.

## Escalate

If the service does not return to a COMPLETED deployment within 20 minutes, or old tasks stop serving, page the SRE on-call and post in the SRE team channel with the run link and the `describe-services` output. A deployment stalls when the circuit breaker has no COMPLETED deployment to return to. Pointing the service at a known good revision ([Roll back to an earlier revision](#roll-back-to-an-earlier-revision)) starts a new deployment.

## Rehearsals

| Date | Defect | Time to FAILED | Time to rollback COMPLETED | Notes |
| --- | --- | --- | --- | --- |
| | | | | Not rehearsed yet: TASK-111.16 Definition of Done. |
