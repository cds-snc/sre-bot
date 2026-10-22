---
id: TASK-111.16
title: >-
  Roll back failed deploys: ECS deployment circuit breaker and immutable image
  tags
status: In Progress
assignee: []
created_date: '2026-10-21T20:05:00Z'
updated_date: '2026-10-22T17:12:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.4
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
  - terraform/ecs.tf
  - .github/workflows/build_and_deploy.yml
parent_task_id: TASK-111
ordinal: 424000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The configuration and lifecycle ADRs rely on the ECS deployment circuit breaker rolling a failed deploy back to the previous task-definition revision (configuration.md "Renaming an environment name", lifecycle.md "Fail fast on deploy-coupled defects"). Production has neither half: aws_ecs_service.main has no deployment_circuit_breaker block (only CPU/memory alarm rollback), and the task definition runs sre-bot:latest while build_and_deploy.yml pushes :latest and forces a new deployment of the same revision, so the previous revision runs the same broken image. Today a deploy that fails boot hangs (old tasks keep serving under the default 100% minimum healthy), the workflow posts a failure to Slack after about 15 minutes, and recovery is a manual retag of the previous <sha>-<date> image as latest.

This lands before TASK-111.7, the first deploy that switches a slice to the renamed names, so every later 111.x deploy rolls back on its own.

Planning decides, with current sources: how the deploy workflow registers a task-definition revision pinned to the immutable <sha>-<date> tag while terraform keeps owning the task definition (for example ignore_changes on the service task_definition with the workflow rendering each revision, or terraform taking the image tag as an input), ECR tag immutability for the sha tags, and how a revert-and-redeploy or a manual rollback to a named tag works afterwards.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 aws_ecs_service.main enables deployment_circuit_breaker with rollback
- [x] #2 Each deploy runs a task-definition revision whose image is pinned to that build's digest (<registry>/sre-bot@sha256:<digest>) resolved from ECR, so a rollback to the previous revision runs the previous image; tag and digest are in the run summary
- [x] #3 terraform and the deploy workflow do not fight over the task definition: a tf apply after a deploy does not revert the running image; track_latest stays false and skip_destroy is true on aws_ecs_task_definition
- [x] #4 decisions/deployment.md records ownership, image identity, ECR policy and retention, the circuit breaker, serialization, rollback and rehearsal; configuration.md, lifecycle.md (including the corrected breaker counting), health-checks.md and cloud-portability.md link to it; the decisions README lists it; each touched record has a dated Changes line
- [x] #5 docs/runbooks/roll-back-a-deployment.md documents dispatch rollback (tag validated and resolved to digest), the CLI fallback, redeploying the current image after a terraform task-definition change, and the post-deploy Verify checklist; it links deployment.md and has owner and last_reviewed; governance.md records the docs/runbooks convention
- [x] #6 The PR's tf plan shows only the expected service, ECR repository and state-only task-definition changes; nothing replaced or destroyed; nothing applied before merge
- [x] #7 The deploy workflow fails when the service ends on a task definition other than the one this run registered or the PRIMARY deployment rolloutState is FAILED; the Slack message names the rollback (circuit breaker or alarm) and links the run
- [ ] #8 When the sha tag already exists the job builds and pushes nothing, reuses that digest and leaves latest unmoved; ECR rejects overwriting a sha tag while latest stays pushable
- [x] #9 The SBOM step scans the deployed tag/digest, and docker_vulnerability_scan.yml accepts an image_tag dispatch input defaulting to latest
- [x] #10 Concurrency groups ecs-deploy (build_and_deploy deploy job) and terraform-apply (tf_apply.yml) both use queue: max
- [ ] #11 health_check_grace_period_seconds is set above the measured boot time (measurement in the notes) and the tf plan shows it as an in-place change
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Human: after merge, tf_apply succeeded and the in-place UpdateService started no deployment
- [x] #2 Human: one happy-path dispatch deploy done, so a workflow-registered COMPLETED revision exists
- [ ] #3 Human: off-hours rehearsal with an invalid-ENVIRONMENT revision: breaker FAILED, rolled back to the previous revision, verify step fails and notifies
- [ ] #4 Human: rehearsal timings and date recorded in the runbook before TASK-111.5.2 or TASK-111.7 merges
- [x] #5 Human: sre-bot-apply IAM permissions confirmed before merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STATUS: APPROVED (human, 2026-10-22). Option A.

## Decisions recorded
- Ownership: Option A. The deploy workflow registers each task-definition revision; terraform owns everything else, with lifecycle ignore_changes=[task_definition] on aws_ecs_service.main. Options B (terraform takes the tag as a variable) and C (rely on ECS version consistency) were rejected: B makes every app deploy a full terragrunt apply and has no tag source for terraform-only PRs; C is not documented to make a rollback relaunch the previous digest (ECS docs: deployment-type-ecs "Container image resolution", ServiceRevision API) and leaves AC #2 unmet.
- Image identity: each revision runs <registry>/sre-bot@sha256:<digest>, resolved with `aws ecr describe-images --image-ids imageTag=$IMAGE_TAG`; tag and digest are written to $GITHUB_STEP_SUMMARY. Tag stays <sha>-<date>, computed once. :latest is a convenience pointer only.
- New ADR decisions/deployment.md (not a lifecycle paragraph). Runbook docs/runbooks/roll-back-a-deployment.md starts the docs/ folder.
- SIZE GATE EXCEPTION, human-approved: about 13 files (limit ~10) and roughly 250 changed LOC. Accepted because the changes are tied together (ADR, runbook and conventions describe the mechanism the code lands) and 7 of the 13 are small docs. Two subsystems (terraform, CI) plus docs; no mechanical refactor mixed in; one git revert restores behaviour (caveat below).
- Provider hashicorp/aws 6.56.0 (terraform/.terraform.lock.hcl:5; 6.70.0 behaves the same here), Terraform 1.16.6, terragrunt 0.48.0.

## Call sites
- terraform/ecs.tf:10-35 (task def: skip_destroy=true; track_latest stays false/unset; image :latest line 23 is only a render base), :37-73 (service: deployment_circuit_breaker, lifecycle ignore_changes=[task_definition], health_check_grace_period_seconds; alarms 63-68 stay)
- terraform/ecr.tf:1-8 (IMMUTABLE_WITH_EXCLUSION, filter latest)
- terraform/alb.tf:10-17 (target group health check: unhealthy after ~20s), terraform/templates/sre-bot.json.tpl:20-29 (container healthCheck startPeriod 10, interval 30, retries 3) -- read for grace-period sizing
- .github/workflows/build_and_deploy.yml:8-14 (paths-ignore), 40 (role), 52-64 (build/push, two `date` calls), 66-79 (restart + sleep/wait), 82-104 (notifications, Sentinel), 111 (SBOM :latest)
- .github/workflows/tf_apply.yml:3-9, 45 (add concurrency); tf_plan.yml (read: PR plan comment)
- .github/workflows/docker_vulnerability_scan.yml:43 (:latest; add image_tag dispatch input)
- decisions/configuration.md:45 (+Changes line after :114), decisions/lifecycle.md:37, :47 (+Changes line after :90), decisions/cloud-portability.md:29 (link), decisions/health-checks.md (grace period, +Changes line), decisions/governance.md:28 (docs/runbooks convention, +Changes line), decisions/README.md (index row)
- New: decisions/deployment.md, docs/runbooks/roll-back-a-deployment.md
- bin/ has only backlog_issue_sync.py: nothing deploy-related.

## Steps
1. terraform/ecs.tf service: add deployment_circuit_breaker {enable=true, rollback=true}; lifecycle {ignore_changes=[task_definition]}; health_check_grace_period_seconds = <measured boot time + margin, ~60 expected; measure from startup `phase` logs in CloudWatch (/ecs/sre-bot-app) before choosing; verify the AWS grace-period wording at implementation: the period applies to ELB health checks only, and the container startPeriod must be shorter than it>. Breaker stays at AWS defaults: provider exposes only enable/rollback (not thresholdConfiguration/resetOnHealthyTask added by AWS 2026-07-01); at desired_count 2 the threshold clamps to 3. Revisit trigger goes in the ADR. If measured time-to-rollback exceeds 10 minutes, raise the wait to 20.
2. terraform/ecs.tf task def: skip_destroy=true (a terraform replacement must never deregister a revision that may be a rollback target; INACTIVE revisions cannot be assigned to a service) and track_latest stays false (true would make terraform diff against the workflow's revisions and re-register on every apply). Record both reasons in a code comment and the ADR.
3. terraform/ecr.tf: image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION" with one filter {filter="latest", filter_type="WILDCARD"}. No lifecycle policy (retention: no expiry). IAM: needs ecr:PutImageTagMutability for the apply role.
4. build_and_deploy.yml, tag and build: compute IMAGE_TAG=<sha>-<date> once (step output). Check `aws ecr describe-images --image-ids imageTag=$IMAGE_TAG`: if the tag EXISTS, skip build and push entirely, reuse its digest, and do NOT move latest. Only when a new image was pushed, push the sha tag then move latest. Resolve the digest after push (or from the existing image) and fail if empty.
5. build_and_deploy.yml, deploy: render (aws-actions/amazon-ecs-render-task-definition, task-definition-family sre-bot-task, container-name sre-bot, image = registry/sre-bot@sha256:digest) then deploy (aws-actions/amazon-ecs-deploy-task-definition, wait-for-service-stability, wait-for-minutes 15, continue-on-error). Both actions pinned by commit SHA (current: render v1.9.1, deploy v2.6.4; resolve SHAs at implementation). Replaces lines 66-79. Write tag and digest to $GITHUB_STEP_SUMMARY.
6. Verify step after the wait. The services-stable waiter also succeeds after a rollback (the service stabilises on the old revision), so the step fails when (a) describe-services .taskDefinition != the ARN this run registered, or (b) the PRIMARY deployment rolloutState is FAILED. Read rolloutStateReason into the message. Slack failure text: "rolled back (circuit breaker or alarm)" with the run link. Consider polling describe-services for FAILED during the wait to report early. Sentinel report and success Slack require verified success.
7. build_and_deploy.yml, manual rollback: workflow_dispatch input `image_tag` (documented: empty = build main; set = roll to that existing tag, no build). Validated against ^[0-9a-f]{40}-[0-9]{4}-[0-9]{2}-[0-9]{2}$ (real tag format), confirmed in ECR and resolved to a digest before registering; the input reaches the shell only through env:, never interpolated into run:. Jobs split into build (skipped when image_tag set) and deploy.
8. SBOM step (build_and_deploy.yml:111) scans the deployed tag/digest, not :latest. docker_vulnerability_scan.yml:43 gets an `image_tag` dispatch input defaulting to `latest`.
9. Concurrency: deploy job group `ecs-deploy` with `queue: max` (GitHub changelog 2026-05-07; cancel-in-progress false would drop a pending rollback dispatch). tf_apply.yml gets its own group `terraform-apply` with `queue: max`. Separate groups, not shared: they write disjoint things, and a group serialises without ordering. Verify `queue: max` syntax against current GitHub docs at implementation.
10. IAM (human, sre-bot-apply is not defined in this repo; no GitHub `environment:` because it changes the OIDC sub claim and the trust policy is unknown): confirm ecs:RegisterTaskDefinition, ecs:DescribeTaskDefinition, ecs:DescribeServices, ecs:UpdateService, ecr:DescribeImages, ecr:PutImageTagMutability (terraform side), iam:PassRole on aws_iam_role.sre-bot (terraform/iam.tf:77, used as execution and task role at ecs.tf:12,17). If missing, an additive policy joins this PR.
11. decisions/deployment.md (governance.md format: 4 frontmatter fields, under ~150 lines, executable Checks, Changes list, README row). Sections: Ownership (terraform owns all but the running revision; ignore_changes; terraform task-definition changes reach production at the next deploy, runbook says redeploy the current image); Image identity (tag + digest pin; latest is a pointer only); ECR (IMMUTABLE_WITH_EXCLUSION latest; no expiry; any future lifecycle policy is count-based and keeps every image referenced by an ACTIVE revision); Circuit breaker (defaults and why, alarms stay, success = service ends on the registered revision and COMPLETED); Serialization (two groups); Manual rollback (procedure in the runbook; a rollback leaves main unchanged so revert or fix forward first; CLI fallback `aws ecs update-service --task-definition sre-bot-task:<rev>`); Rehearsal (once in production off-hours before the first dependent deploy and on mechanism change, with an invalid ENVIRONMENT revision; timings recorded in the runbook; AWS Well-Architected REL12-BP05/04). At most 3 sources. Since the PR lands the code, status applies now provided Checks pass.
12. Pointers: configuration.md:45 (+Changes line), lifecycle.md:37 and :47 (+Changes line; :47 corrected: the breaker counts tasks that fail to reach RUNNING and tasks replaced for failed load-balancer or container health checks; at 2 replicas it trips after 3 consecutive failures; it rolls back to the last COMPLETED deployment), cloud-portability.md:29 (link, cascade), health-checks.md (grace period above measured boot time, container startPeriod below the grace window; Changes line), README row.
13. governance.md:28: decisions/ = why + binding rule; docs/runbooks/ = how-to (one per file, verb-first kebab name); an ADR links its runbook and never carries steps, a runbook links its ADR and never carries rationale; backlog/docs/ = planning; add other docs/ subfolders only when a second kind exists; the cascade rule extends to runbooks; dated Changes line and README pointer.
14. docs/runbooks/roll-back-a-deployment.md: frontmatter title, owner, last_reviewed, decisions; sections When to use, Permissions and tools, Steps, Verify, Escalate. Covers: dispatch rollback (tag validated, resolved to digest), CLI fallback, "redeploy the current image after a terraform task-definition change", and the recurring post-deploy checklist (from the 111.5.1 and 111.6.x notes) as Verify. Records rehearsal date and timings after DoD step 4.

## AC traceability
#1 step 1 (tf plan; describe-services post-merge) · #2 steps 3-5 (rehearsal summary shows tag+digest; describe-task-definition image is @sha256) · #3 steps 1-2 (tf plan after a deploy shows no change to service task_definition or task definition) · #4 steps 11-13 (diff; Checks in the ADR) · #5 steps 7, 14 · #6 tf_plan.yml posts the plan on the PR (pull_request, terraform/**); tf_apply.yml runs only on push to main; expected: in-place aws_ecs_service.main (breaker, grace period), in-place aws_ecr_repository.sre-bot, state-only task-definition skip_destroy update; nothing replaced or destroyed · #7 step 6 · #8 steps 3-4 · #9 step 8 · #10 step 9 · #11 step 1.

## Verification matrix (no app tests change; terraform and workflows have no unit tests here)
- Happy path: dispatch deploy -> new revision with @sha256 image, stable, verify passes, summary has tag+digest.
- Boundary: rerun on the same commit and day -> tag exists, no build/push, latest unmoved, digest reused; image_tag with bad format or missing in ECR -> fails before registering; image_tag injection attempt (shell metacharacters) rejected by the regex.
- Failure: off-hours rehearsal with a revision that has an invalid ENVIRONMENT -> breaker FAILED, rollback to the previous revision, verify step fails, Slack names the rollback. Also a second tf plan after apply shows zero diff.
- Concurrency: two overlapping dispatches queue; a rollback dispatch is not dropped.
- Lint: actionlint locally if installed; CI has no workflow lint job.

## Assumptions and doubts (verify)
1. sre-bot-apply has the permissions in step 10 (human, aws iam list-attached-role-policies).
2. ignore_changes means unrelated service updates do not send TaskDefinition (read the PR plan; later service edit).
3. ECR filter "latest" exempts only that tag (read plan; try overwriting a sha tag).
4. The render action reads the latest ACTIVE revision by family and strips read-only fields (rehearsal).
5. Time-to-rollback at threshold 3 fits the 15-minute wait (measure; raise to 20 if over 10).
6. Grace period AWS wording and measured boot time (step 1).
7. SSM placeholder values for the 111.4 renamed secrets are set before 111.7; an unset secret now means boot failure then rollback.
8. `queue: max` syntax (step 9).

## Blast radius and rollback
- Merge: tf_apply (the only workflow triggered, since build_and_deploy ignores terraform/.github/decisions/backlog; docs/ is not ignored, so check the paths-ignore list: ADD docs/** to paths-ignore in this PR or the merge deploys the app) does in-place updates only; no task restarts, and the in-place UpdateService starts no deployment (DoD 1 confirms). The new deploy path first runs at the dispatch rehearsal.
- git revert restores the prior workflow and terraform. Caveat: if a rollback to an older tag is in effect, the post-revert apply points the service at terraform's revision (:latest), rolling forward.
- If the workflow is wrong, register/update fails before changing the service, or the breaker rolls back; old tasks keep serving (minimum healthy 100%).
- Ordering: must land and be rehearsed before TASK-111.5.2 and TASK-111.7. Impact on other tasks: TASK-111.15 split (111.15.1 deploy-verified before 111.15.2 removes the IAM read); 111.5.2 AC #6; 111.8-111.13 now depend on 111.16; TASK-72 note (fargate_memory change reaches production at the next deploy).

## Follow-ups (not created)
- Stop pushing :latest and move to plain IMMUTABLE (needs the scan and SBOM paths off :latest, done here for those two).
- Image signing and provenance.
- ECR lifecycle policy (count-based, keeps every image referenced by an ACTIVE revision).
- EventBridge SERVICE_DEPLOYMENT_FAILED alert.
- GitHub `environment:` on the deploy job after reading the sre-bot-apply trust policy.

## Sources
https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html · https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html · https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-revision.html · https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html · https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deregister-task-definition-v2.html · https://github.com/hashicorp/terraform-provider-aws/tree/v6.56.0/website/docs/r · https://github.com/aws-actions/amazon-ecs-deploy-task-definition · https://github.com/aws-actions/amazon-ecs-render-task-definition
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-22 (In Progress). Single PR, file-gate exception approved 2026-10-22.

Changes
- terraform/ecs.tf: service gets deployment_circuit_breaker {enable, rollback}, health_check_grace_period_seconds = 60, lifecycle ignore_changes = [task_definition]; task definition gets skip_destroy = true (track_latest left unset = false). The :latest image stays as the render base.
- terraform/ecr.tf: IMMUTABLE_WITH_EXCLUSION with one WILDCARD filter "latest" (provider 6.56.0 image_tag_mutability_exclusion_filter block).
- build_and_deploy.yml: jobs build / deploy / sbom. build computes IMAGE_TAG once, checks ECR (ImageNotFoundException = absent, any other error fails), builds and pushes the sha tag then latest only when absent, resolves the digest. deploy (concurrency ecs-deploy, queue: max) resolves tag+digest (dispatch input image_tag validated against ^[0-9a-f]{40}-YYYY-MM-DD$, read only through env:), writes both to the run summary, renders from family sre-bot-task (render v1.9.1 @8d79160) with image <registry>/sre-bot@sha256:..., deploys (deploy v2.6.4 @a00d4d5, wait 15 min, continue-on-error), then verify-ecs-deployment.sh. Slack success/failure via jq-built payloads with webhooks in env; failure text carries the verify message and the run URL. Sentinel version = the deployed tag's sha (correct for rollbacks). sbom runs beside deploy on the pushed tag, only when a new image was built, so a trivy-db rate limit no longer reddens a deploy. docs/** added to paths-ignore.
- .github/workflows/scripts/verify-ecs-deployment.sh: fails unless services[0].taskDefinition == the registered ARN and the PRIMARY rolloutState is COMPLETED; message names "rolled back (circuit breaker or alarm)".
- tf_apply.yml: concurrency terraform-apply, queue: max. docker_vulnerability_scan.yml: image_tag input, default latest.
- decisions/deployment.md (new, applies now), README row + docs/runbooks pointer, governance.md docs/runbooks convention, pointers and Changes lines in configuration.md, lifecycle.md (breaker counting corrected), health-checks.md (grace period rule), cloud-portability.md.
- docs/runbooks/roll-back-a-deployment.md (new): roll back to an image (dispatch), redeploy the current image after a terraform task-definition change, roll back to a revision (CLI), Verify (generic checks 1-3 of the 111.5.1/111.6.x checklists, portable date arithmetic), Escalate, empty Rehearsals table.

Verification (evidence)
- terraform fmt clean; terraform validate in a clean scratch copy (init -backend=false, lock file 6.56.0): "Success! The configuration is valid." The repo's terraform/.terraform cache is stale (module source changed), untouched.
- verify-ecs-deployment.sh against canned describe-services JSON: completed -> pass; rolled back (service on :41, registered :42) -> fail with the rollback message; PRIMARY FAILED -> fail; IN_PROGRESS -> fail; empty ARN -> fail. shellcheck v0.7.1 (the repo's runner image): clean.
- actionlint 1.7.12: clean except `unexpected key "queue" for "concurrency"` on both files. GitHub docs (control-workflow-concurrency, read 2026-10-22) document `queue: single|max` (max = up to 100 pending, FIFO, not with cancel-in-progress: true); actionlint's schema predates it. If GitHub rejects it on the PR's workflow validation, drop the line (behaviour then: cancel-in-progress false, one pending run).
- Gates: ruff "All checks passed!"; make check-import-contracts "Contracts: 12 kept, 0 broken."; make check-settings-key-ownership OK; mypy "Found 47 errors in 18 files" = baseline (legacy modules/); pytest 5598 passed. No Python changed.
- AWS docs read 2026-10-22: circuit breaker (BOUNDED_PERCENT 50, min 3; stage 1 and stage 2; rollback target last COMPLETED; stalls without one); service parameters (grace period ignores ELB, VPC Lattice and container checks; updating it, deploymentConfiguration or desiredCount triggers no new deployment).

ACs left open (need production evidence)
- #2: code in place; evidence = run summary + describe-task-definition image @sha256 after the DoD 2 dispatch deploy.
- #6: the PR's tf_plan comment. Expected: in-place aws_ecs_service.main (breaker, grace period), in-place aws_ecr_repository.sre-bot (mutability + filter), aws_ecs_task_definition.sre-bot skip_destroy update with no replacement; nothing destroyed.
- #8: reuse path in code; "ECR rejects overwriting a sha tag" is verifiable only after apply (re-run the same commit's workflow the same day: build skipped, digest reused, latest unmoved).
- #11: no AWS access in this session (InvalidClientTokenId), so boot time was not measured. 60 s chosen: ALB marks unhealthy after ~20 s (interval 10, threshold 2) and the container check startPeriod is 10 s. Human: measure task start -> first ALB healthy from /ecs/sre-bot-app (lifespan phase logs) and adjust if boot exceeds ~45 s.

Not run here: tf plan (no AWS credentials).
Follow-ups (not created): stop pushing latest + plain IMMUTABLE; image signing/provenance; ECR lifecycle policy; EventBridge SERVICE_DEPLOYMENT_FAILED alert; GitHub environment: after reading the sre-bot-apply trust policy.

Merged 2026-10-22 as #1772 (36adb97e, 14:45 UTC). tf_apply run 39798412641, job 119891859541: "Apply complete! Resources: 0 added, 3 changed, 0 destroyed." aws_ecr_repository.sre-bot MUTABLE -> IMMUTABLE_WITH_EXCLUSION + filter latest/WILDCARD; aws_ecs_service.main health_check_grace_period_seconds 0 -> 60, deployment_circuit_breaker enable/rollback false -> true (task_definition not in the diff); aws_ecs_task_definition.sre-bot skip_destroy false -> true, no replacement. AC #6 checked on this. The run stayed "in progress" after its only job completed: GitHub "Incident with Actions Results" (Actions degraded) the same afternoon; the job log was read through the jobs API.
No build/deploy ran (the merge touched only ignored paths); production still runs the #1771 image 80947e62...-2026-10-22 on terraform's :latest revision. Next: human dispatch deploy once Actions is healthy (DoD 2), then ACs 2, 8, 11 and the rehearsal.

Post-apply check 2026-10-22 (human-run): service breaker enable/rollback true (AWS reports resetOnHealthyTask true, BOUNDED_PERCENT 50), alarms unchanged, grace 60; one PRIMARY deployment, COMPLETED, created 13:54:59 UTC (the #1771 deploy) on sre-bot-task:36, last event steady state 14:03 UTC, nothing after the 14:45 apply: no deployment started (DoD 1). ECR IMMUTABLE_WITH_EXCLUSION, filter latest/WILDCARD. sre-bot-task:36 ACTIVE, image :latest, still the latest revision (skip_destroy registered nothing).
Caveat for the first dispatch: the only COMPLETED rollback target (:36) references :latest, and a build moves latest before deploying. First dispatch therefore redeploys the running image by tag (image_tag=80947e62d87ba0eb6eba2c24914be59c0c5675a7-2026-10-22: no build, latest unmoved), which makes a digest-pinned COMPLETED target; the build path runs second.

Rehearsal through the workflow (second PR, 2026-10-22): production changes only through the GitHub Actions workflows (Codespace env differs from the secrets), and the only OIDC role in the repo trusts refs/heads/main, so the rehearsal cannot be a local update-service or a branch dispatch. build_and_deploy gains a boolean dispatch input rehearse_rollback: requires image_tag (no build), the render step overrides ENVIRONMENT=rollback-rehearsal (AppSettings.ENVIRONMENT is Literal local/ci/production, read first in the lifespan, so boot aborts), verify fails as expected, then "Deregister the rehearsal revision" (always) deregisters it once the service has left it, because the next deploy renders from the family's latest revision. Render action v1.9.1 replaces an existing variable of the same name (index.js). Needs ecs:DeregisterTaskDefinition on sre-bot-apply. Runbook gains "Rehearse a rollback" with exact commands; deployment.md Rehearsal paragraph and a Changes line. actionlint clean except the known queue key, which GitHub accepted (tf_apply run 39798412641 ran with queue: max).

Admin-only manual deploys (human 2026-10-22, same PR): any of the 45 users with write access or above could dispatch or re-run build_and_deploy (GitHub requires write access to run a workflow manually). Now .github/workflows/scripts/require-admin.sh runs in the build and deploy jobs, after checkout and before AWS credentials, when the event is workflow_dispatch or run_attempt != 1. It reads github.triggering_actor's role_name from repos/<repo>/collaborators/<actor>/permission and fails unless it is admin. It runs per job because "re-run failed jobs" re-runs only the failed job. Merge deploys stay gated by the main ruleset (1 approval, no bypass actors). Tested against the live API: admin passes; write, read and an unknown user are refused. shellcheck clean. The first manual dispatch confirms GITHUB_TOKEN can read the endpoint (metadata read); if it cannot, the check denies everyone (fails closed). The GitHub-enforced version (environment with required reviewers, which changes the OIDC subject) is TASK-160.

Permissions 2026-10-22 (human-run simulate-principal-policy on sre-bot-apply): ecs:RegisterTaskDefinition, ecs:DeregisterTaskDefinition, ecs:DescribeTaskDefinition, ecs:DescribeServices, ecs:UpdateService, ecr:DescribeImages and iam:PassRole on sre-bot-ecs-role all allowed (DoD 5). Trust condition: token.actions.githubusercontent.com:sub StringLike repo:cds-snc/sre-bot:ref:refs/heads/main and repo:cds-snc@30166251/sre-bot@*:ref:refs/heads/main, so a branch dispatch gets no credentials and require-admin.sh changes need an approved PR to main. TASK-160 must add the environment subject to this condition first.

Fix PR #1773 merged 2026-10-22 16:30 UTC (46f8f603). Dispatch 1 (run 39816764103, image_tag 80947e62d87ba0eb6eba2c24914be59c0c5675a7-2026-10-22) started 16:46 UTC: build and sbom skipped; "Require a repository admin" passed with GITHUB_TOKEN (the permission endpoint is readable, so the check does not fail closed for admins); Resolve image and Render passed. Human reports the new tasks running. Pending: the run's verify result and the describe-task-definition/describe-services output for AC #2 and DoD 2; dispatch 2, the same-day rerun (AC #8), boot time (AC #11) and the rehearsal (DoD 3-4) not run yet.
Dispatch 1 result: run 39816764103 success. Render used sre-bot@sha256:88fc35f816cfc955589c369757624926f97a2d680d99fa6cf9ce147b9ffc1a17 (tag 80947e62d87ba0eb6eba2c24914be59c0c5675a7-2026-10-22, also in the run summary from Resolve image); verify: "The service runs sre-bot-task:37 and its deployment completed."; Slack success and Sentinel ran. Human describe-services: one PRIMARY, COMPLETED, created 16:47 UTC on sre-bot-task:37; production up. AC #2 and DoD 2 checked: :37 is the first digest-pinned COMPLETED rollback target. Open: AC #8 (same-day rerun of a build run), AC #11 (boot time), DoD 3-4 (rehearsal, deferred by the human; gates the 111.5.2 merge).

Rehearsal hardening (third PR, 2026-10-22; the human rehearses in working hours with notice): the deregister step now always deregisters the rehearsal revision, then fails with the recovery command if the service still runs it. Before, it skipped deregistration in that case, so a recovery dispatch would have rendered from the broken revision. AWS: an INACTIVE revision keeps its running tasks and service without disruption. The step runs under always(), so cancelling the run deregisters too. Runbook "Rehearse a rollback" rewritten as the exact sequence (starting point, dispatch, watch, check, record) with recovery: cancel, then redeploy the running tag, then break-glass update-service to the recorded revision. deployment.md: no off-hours requirement; Changes line.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-22T13:25:00Z

---

Proposed AC rewording (not applied): #6 reads 'only the expected service and task-definition changes'; under option A the plan shows in-place changes to aws_ecs_service.main and aws_ecr_repository.sre-bot and at most a skip_destroy update on the task definition. Suggest 'only the expected service, ECR repository and (state-only) task-definition changes; no resource replaced or destroyed; nothing applied before merge'. Keep #3 as is. Removals: none.

---
<!-- COMMENTS:END -->
