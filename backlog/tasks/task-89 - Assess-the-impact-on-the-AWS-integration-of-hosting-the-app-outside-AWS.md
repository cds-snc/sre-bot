---
id: TASK-89
title: Assess the impact on the AWS integration of hosting the app outside AWS
status: To Do
assignee: []
created_date: '2026-09-11 15:49'
updated_date: '2026-09-24 20:11'
labels:
  - architecture
dependencies: []
references:
  - app/integrations/aws/client.py
  - decisions/cloud-portability.md
  - decisions/workplace-systems.md
  - decisions/outbound-clients.md
  - decisions/plugin-architecture.md
priority: medium
type: spike
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Spike (created 2026-09-11 during the TASK-25.2 reassessment). The AWS vendor client (app/integrations/aws/client.py) needs no credentials of its own because the SRE Bot runs inside an AWS account and uses boto3's ambient credential chain, unlike the Google Workspace client, which carries a service-account key. That assumption is implicit and undocumented.

AWS plays two roles for this app: hosting provider (DynamoDB, Secrets Manager, ECS) and the target system of several Path B business features (Identity Center administration, access requests via SSO-Admin, Organizations and account-health reporting, Lambda inventory). decisions/workplace-systems.md states that leaving AWS touches only hosting implementations; that holds for the hosting role but not for the second role, which must keep reaching AWS from wherever the app runs.

Assess, for a hypothetical move of hosting to another cloud (e.g. Azure): how the client obtains credentials (OIDC / workload identity federation into an IAM role vs static keys vs a proxy account), whether get_aws_client's eager AssumeRole and role ARN settings still fit, which settings would then become required and whether they belong in integrations/aws/settings.py (transport, per decisions/outbound-clients.md) or in feature settings, and what changes in decisions/cloud-portability.md and decisions/workplace-systems.md. Output is a written assessment and a decision-record amendment proposal (at most one short dated sentence per changed decision, amended in place), not code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A written assessment covers credential acquisition options, the fit of the current factory (eager AssumeRole, role ARN settings) and the settings that would become required, with sources cited
- [ ] #2 A proposed amendment to decisions/cloud-portability.md and/or decisions/workplace-systems.md distinguishes AWS as hosting provider from AWS as a Path B target system
- [ ] #3 The implicit ambient-credentials assumption is documented where the human decides it belongs (decision record or client.py module docstring)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 18:57
---
FIELD EVIDENCE 2026-09-17 (main @ 27fb2bda): the spike's central question is already answerable from a live failure, and one of its premises needs correcting.

PREMISE TO CORRECT. The description says the AWS client "needs no credentials of its own because the SRE Bot runs inside an AWS account and uses boto3's ambient credential chain". That is true only for the no-role path. Where a role ARN is configured, integrations/aws/client.py:154/:181/:192 performs a live sts:AssumeRole AT CLIENT CONSTRUCTION (docstring at :147-149: "assumes that role eagerly through STS before the client is built"). So the app depends on ambient credentials AND on STS reachability, at construction time, not at first call.

LOCAL DEVELOPMENT IS ALREADY AN INSTANCE OF "HOSTING OUTSIDE AWS". A developer machine with no ambient AWS credentials is exactly the credential situation of a non-AWS host, and the app does not boot there today:
  botocore.exceptions.ClientError: An error occurred (InvalidClientTokenId) when calling
  the AssumeRole operation: The security token included in the request is invalid.
Chain: server/lifespan.py:188 auto_discover_plugins -> packages/access/sync/__init__.py:83 startup_warmup
-> providers.py:64/:38 -> adapters/aws_identity_center.py:1226 get_aws_client("identitystore", role_arn=...)
-> integrations/aws/client.py:192 sts.assume_role(...). "import main" alone succeeds; the failure is in lifespan.
Triggered when ACCESS_SYNC_ENABLED=true (set in the developer .env), AWS_ORG_ACCOUNT_ROLE_ARN is non-empty
(settings.py:107 defaults to "", mapped by SERVICE_ROLE_MAP["identitystore"] at :118; an empty ARN skips
AssumeRole and boot survives), and no valid credentials are present. The devcontainer exports that ARN.

CONSEQUENCE FOR AC#1's "fit of the current factory". The answer is already partly negative and does not need a hypothetical Azure move to demonstrate it: eager AssumeRole makes AWS STS a HARD BOOT DEPENDENCY of the whole service, including for the Path B business-feature role the description separates out. On a non-AWS host the credential-acquisition options the spike must weigh (OIDC / workload identity federation, static keys, proxy account) all still have to produce a usable credential BEFORE the process can start serving anything, because a feature adapter is built during lifespan. Any option that acquires credentials lazily or can fail transiently is incompatible with the current factory as written. Whether the fix is lazy client construction, non-fatal feature warmup, or both is TASK-92's call (see below), but the assessment should state the constraint explicitly.

EVIDENCE THAT THE TREE ALREADY WORKS AROUND IT. app/pyproject.toml:107-111 pins "ACCESS_SYNC_ENABLED=false" for the test suite, commented: "ACCESS_SYNC_ENABLED=true would make lifespan build the AWS Identity Center adapter (and assume its role) at startup."

SCOPE BOUNDARY WITH TASK-92. TASK-92 (To Do) AC#1 explicitly owns reconciling "eager AssumeRole in get_aws_client" with startup validation, and its AC#5 owns where connectivity warmup belongs. This spike should NOT re-decide that; it should assume TASK-92's outcome as an input and confine itself to credential ACQUISITION off-AWS plus where the resulting settings live (integrations/aws/settings.py transport vs feature settings, per decisions/outbound-clients.md). The two must not reach contradictory conclusions about get_aws_client. No dependency wired between the tasks; left for the human.

POSSIBLE AC GAP (raised, not acted on): no current AC covers local development as the everyday non-AWS-host case, or what a developer without AWS credentials is supposed to be able to run. If the human wants that in scope it needs its own AC; it is not implied by #1, #2 or #3.
---

created: 2026-09-17 19:08
---
FOLLOW-UP 2026-09-17, investigation completed (same session as the earlier comment). Three additions:

PRODUCTION POSTURE, which bounds this spike's urgency. terraform/templates/sre-bot.json.tpl:52-68 supplies only BACKEND_URL, ENVIRONMENT, CORS_ALLOWED_ORIGINS and SLACK__COMMAND_PREFIX, plus one secret (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE); terraform/ssm.tf holds only the GCP key. Neither ACCESS_SYNC_ENABLED nor AWS_ORG_ACCOUNT_ROLE_ARN appears anywhere under terraform/. Production therefore boots today with access sync disabled and never performs the boot-time AssumeRole. The failure is local-development-only for now and becomes a production boot failure when access sync is enabled. Note the contrast this spike should draw on: the ONE credential the deployment does inject is the Google service-account key, precisely because Google is not the hosting provider -- which is the shape AWS would take on a non-AWS host.

MEASURED INVENTORY OF BOOT-TIME VENDOR I/O (socket-instrumented, credentials unset). directory_provider.warmup() reaches admin.googleapis.com and oauth2.googleapis.com but is gated by DIRECTORY_REQUIRE_STARTUP_WARMUP, which defaults to FALSE (infrastructure/directory/settings.py:41, "Opt in to fail-fast startup validation against the remote directory"). get_aws_client with a role ARN reaches STS with NO equivalent opt-out. get_aws_client without a role ARN, get_directory_provider() construction and jwks_manager.warmup() all perform zero network I/O. So the Google path already has the opt-in switch the AWS path lacks -- relevant to AC#1's "fit of the current factory", since a non-AWS host would need exactly such a switch plus a credential source.

NEW RELATED TASK: TASK-98 (created 2026-09-17, depends on TASK-92). Eager AssumeRole is uncached and runs per adapter build, so every AWS call site pays an STS round-trip (two for builders that construct both a retrying and a retries-disabled client). Off-AWS that round-trip would also cross a cloud boundary on every operation, which sharpens AC#1's credential-acquisition comparison: any federation option must be evaluated for whether credentials can be cached and refreshed, not just acquired once. This spike should reference TASK-98's outcome rather than re-deciding caching.

DIVISION OF OWNERSHIP, restated so the three tasks do not collide: TASK-92 AC#1/AC#5 owns whether AssumeRole may happen at boot at all; TASK-98 owns credential reuse at runtime; this spike owns how credentials are OBTAINED on a non-AWS host and where the resulting settings live. TASK-25.2.6 separately owns retiring the duplicate AWS settings home (infrastructure/configuration/integrations/aws.py vs integrations/aws/settings.py) and already anticipates recording the eager-AssumeRole choice in decisions/outbound-clients.md.
---

created: 2026-09-17 19:15
---
CORRECTION 2026-09-17 to the PRODUCTION POSTURE paragraph in the preceding comment. That paragraph is withdrawn: it concluded from terraform/templates/sre-bot.json.tpl and terraform/ssm.tf that "production therefore boots today with access sync disabled". The ECS task definition is not the only configuration source. app/bin/entry.sh:3-4 fetches two SSM parameters at container start and writes them into .env before uvicorn runs:
  aws ssm get-parameter --name sre-bot-config             ... > ".env"
  aws ssm get-parameter --name sre-bot-config-infrastructure ... >> ".env"
terraform/iam.tf:32-33 grants read on exactly those two ARNs, but terraform/ssm.tf manages only gcp_sre_service_account_key, so their contents are outside version control and unknowable from this repo. SLACK_ENABLED also defaults to false yet must be true in production, which is direct evidence the SSM bundle carries feature flags. Whether production sets ACCESS_SYNC_ENABLED and AWS_ORG_ACCOUNT_ROLE_ARN is therefore UNKNOWN and must be checked against SSM, not inferred from terraform.

WHAT SURVIVES THE CORRECTION, and is in fact sharper for this spike. The only credential the deployment injects through a managed, reviewable channel is the Google service-account key (terraform/ssm.tf, surfaced as the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE secret in the task definition). AWS needs no such channel today only because the app runs inside AWS and inherits the task role. That is the implicit assumption AC#3 asks to document, and it is the one that breaks on a non-AWS host: AWS would then need a managed credential channel of its own, and the Google key is the worked example of what that looks like in this deployment.

ALSO RELEVANT TO AC#1's "which settings would then become required". Those settings would land in a hand-edited SSM blob that no terraform resource manages and no review covers. The assessment should say where AWS credential settings belong in the deployment, not only where they belong in the code (integrations/aws/settings.py vs feature settings).
---

created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). Leaving AWS touches only app/infrastructure/ implementations of app/contracts/ Protocols plus integrations/aws; features and capabilities never see the cloud (plugin-architecture.md Consequences).
---
<!-- COMMENTS:END -->
