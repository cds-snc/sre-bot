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

- GitHub: the repository **admin** role. Manual runs and re-runs of `build_and_deploy.yml` fail at "Require a repository admin" for anyone else; ask an admin to run it.
- In a Codespace, `gh` uses the Codespace token, which cannot start workflows (`HTTP 403: Resource not accessible by integration`). Start runs from the workflow page (**Run workflow**, branch `main`, fill the inputs) or log in once with your own account: `env -u GITHUB_TOKEN -u GH_TOKEN gh auth login --web --scopes workflow`, then prefix `gh workflow run` and `gh run cancel` with `env -u GITHUB_TOKEN -u GH_TOKEN`. Reading runs works with either.
- AWS CLI fallback: a role with `ecs:DescribeServices`, `ecs:ListTaskDefinitions`, `ecs:DescribeTaskDefinition`, `ecs:UpdateService` and `ecr:DescribeImages` on the production account.

## Steps

### Find the image tags

Each run's summary lists the deployed tag (`<git sha>-<YYYY-MM-DD>`) and digest. To list the newest tags in ECR:

```bash
aws ecr describe-images --region ca-central-1 --repository-name sre-bot \
  --query 'sort_by(imageDetails,&imagePushedAt)[-5:].[imagePushedAt,imageTags,imageDigest]' --output table
```

### Roll back to an earlier image

1. Run the workflow on `main` with the earlier tag (or GitHub, Actions, **Build and Push to Container Registry**, **Run workflow**):

   ```bash
   gh workflow run build_and_deploy.yml --ref main -f image_tag=<git sha>-<YYYY-MM-DD>
   gh run watch "$(gh run list --workflow build_and_deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
   ```

2. The run checks the tag format, resolves the tag to its digest, builds nothing, and deploys a new revision that pins that digest. It fails if the service does not end on that revision.
3. `main` is unchanged, so the next merge deploys forward again. Revert or fix forward on `main` before that merge.

### Redeploy the current image

Run the same command with `image_tag` set to the tag running now (the latest run summary, or [Find the image tags](#find-the-image-tags)). The new revision starts from the family's latest revision, so it carries the terraform change.

### Roll back to an earlier revision

Break-glass only: production changes go through the workflow. Use this when the workflow is unavailable, or when the task definition itself is bad. It points the service at a revision that is already registered, so nothing from the local environment reaches production.

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

## Rehearse a rollback

Expected impact: none. The old tasks keep serving throughout (minimum healthy 100%), and the rehearsal tasks never pass a health check, so the load balancer never routes to them. Announce it anyway; the run fails by design and posts a Slack failure. Use one terminal so the variables carry over. Merges to `main` queue behind the rehearsal; hold them until it ends.

1. Record the starting point. The running revision is the rollback target the circuit breaker must return to:

   ```bash
   CURRENT_TD=$(aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service \
     --query 'services[0].taskDefinition' --output text); echo "$CURRENT_TD"
   aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service \
     --query 'services[0].deployments[].[status,rolloutState,taskDefinition]' --output table   # one PRIMARY, COMPLETED
   DIGEST=$(aws ecs describe-task-definition --region ca-central-1 --task-definition "$CURRENT_TD" \
     --query 'taskDefinition.containerDefinitions[0].image' --output text | cut -d@ -f2); echo "$DIGEST"
   TAG=$(aws ecr describe-images --region ca-central-1 --repository-name sre-bot --image-ids imageDigest="$DIGEST" \
     --query 'imageDetails[0].imageTags[?@ != `latest`] | [0]' --output text); echo "$TAG"
   ```

   Stop if the deployment is not COMPLETED or `TAG` is empty.

2. Start the rehearsal and note the time:

   ```bash
   date -u +%H:%M:%S
   gh workflow run build_and_deploy.yml --ref main -f image_tag="$TAG" -f rehearse_rollback=true
   sleep 15; RUN=$(gh run list --workflow build_and_deploy.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); echo "RUN=$RUN"
   ```

3. Watch the service, every minute or so, until a new deployment on `$CURRENT_TD` is COMPLETED. Expected within about 10 minutes: tasks of the new revision stop at boot, the rehearsal deployment turns FAILED ("circuit breaker"), and a rollback deployment on `$CURRENT_TD` runs, then completes.

   ```bash
   aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service \
     --query 'services[0].deployments[].[status,rolloutState,rolloutStateReason,taskDefinition,runningCount,desiredCount]' --output table
   aws ecs describe-services --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service \
     --query 'services[0].events[:10].[createdAt,message]' --output table
   curl -s -o /dev/null -w '%{http_code}\n' https://sre-bot.cdssandbox.xyz/version   # 200 throughout
   ```

4. Check the run ended as designed: "Verify the deployed revision" failed with "Deployment rolled back (circuit breaker or alarm)", "Deregister the rehearsal revision" passed, and the Slack failure was posted. Then confirm the family's latest revision is clean again:

   ```bash
   gh run watch "$RUN"
   gh run view "$RUN" --json jobs --jq '.jobs[]|select(.name=="deploy")|.steps[]|"\(.name): \(.conclusion)"'
   aws ecs describe-task-definition --region ca-central-1 --task-definition sre-bot-task \
     --query 'taskDefinition.[revision,containerDefinitions[0].environment[?name==`ENVIRONMENT`].value | [0]]' --output text   # production
   ```

5. Run [Verify](#verify) checks 2 to 4, add a row to [Rehearsals](#rehearsals) with the times from step 3, and update `last_reviewed`.

**If the service has not returned to `$CURRENT_TD` after 10 minutes** (the old tasks are still serving; nothing is down):

1. Cancel the run. Its deregister step still runs and removes the rehearsal revision:

   ```bash
   gh run cancel "$RUN"; sleep 20
   gh run view "$RUN" --json jobs --jq '.jobs[]|select(.name=="deploy")|.steps[]|select(.name|test("Deregister"))|"\(.name): \(.conclusion)"'
   ```

2. Redeploy the image that was running. It renders from the clean revision and replaces the rehearsal deployment:

   ```bash
   gh workflow run build_and_deploy.yml --ref main -f image_tag="$TAG"
   sleep 15; RECOVER=$(gh run list --workflow build_and_deploy.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')
   gh run watch "$RECOVER" --exit-status
   ```

3. Break-glass, only if GitHub Actions is unavailable: point the service at the revision that was running. It is already registered, so nothing from the local environment reaches production.

   ```bash
   aws ecs update-service --region ca-central-1 --cluster sre-bot-cluster --service sre-bot-service --task-definition "$CURRENT_TD" > /dev/null
   aws ecs wait services-stable --region ca-central-1 --cluster sre-bot-cluster --services sre-bot-service
   ```

Record what happened in the Rehearsals row either way: a breaker that does not trip on a boot failure is the finding the rehearsal exists to surface.

## Rehearsals

| Date | Defect | Time to FAILED | Time to rollback COMPLETED | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-22, 17:26 UTC (working hours, announced) | `ENVIRONMENT=rollback-rehearsal` on sre-bot-task:38, image of :37 | 3 tasks exited at boot; FAILED before 17:32 | 17:32:15, about 5 min after the 17:27:09 deploy start; back on sre-bot-task:37 | Run 39822672570. Verify failed with "Deployment rolled back", :38 deregistered, Slack failure posted. Old tasks served throughout. Fits the 15-minute wait; no change. |
