---
id: TASK-92
title: >-
  Decide the service health model: no network I/O at boot, static liveness and
  readiness, and plugin boot-failure policy
status: Done
assignee: []
created_date: '2026-09-14 14:55'
updated_date: '2026-09-25 16:13'
labels:
  - architecture
  - clients
  - observability
milestone: m-4
dependencies: []
references:
  - decisions/lifecycle.md
priority: medium
ordinal: 199000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ANALYSIS + DECISION-RECORD TASK (no production code). Rewritten 2026-09-25 against decisions/plugin-architecture.md (accepted 2026-09-24). Planning from before that rework, including the comments below dated 2026-09-17, is superseded where it conflicts with this text. TASK-29 is archived; TASK-109 replaced it.

WHY THIS GATES THE CRITICAL PATH. TASK-109 (svcs registry) resolves every core service at boot and 'runs its health check' (decisions/dependency-injection.md). Whether that check may call the network decides what TASK-109 builds. Nothing else in this ticket gates TASK-109.

EVIDENCE (measured 2026-09-17 under a socket.connect spy):
- Only two boot paths make network calls: the opt-in directory warmup (DIRECTORY_REQUIRE_STARTUP_WARMUP) and access/sync's startup_warmup, whose adapter assumes an AWS role through STS inside get_aws_client. The JWKS warmup only builds clients (net=0).
- The AssumeRole path aborts boot with InvalidClientTokenId when ACCESS_SYNC_ENABLED=true, a role ARN is set and no valid credentials exist. A business feature the SRE Bot does not require takes the whole app down.
- uvicorn runs lifespan startup before it opens its listening socket (uvicorn/server.py startup before create_server), so any response from a static endpoint already means every startup phase completed.
- The ECS deployment circuit breaker counts tasks that never reach RUNNING and rolls back. The ALB fails open when all targets are unhealthy. A dependency in a platform health check becomes a hard, fleet-wide dependency (AWS Builders' Library).
- Backstage's backend, the reference for plugin-architecture.md, aborts on any plugin boot failure by default and lets configuration set backend.startup onPluginBootFailure: continue per plugin.

DECISIONS (human, 2026-09-25):
1. Only deploy-coupled defects abort boot. Construction and settings validation stay static, and client factories do no network I/O (lazy AssumeRole, TASK-98). State that changes without a deploy (IAM role or permission removed, secret rotated, vendor down) never aborts boot: with desired_count = 2, rollback on and 100% minimum healthy (terraform/ecs.tf), a failed deploy keeps serving from the old tasks, but a restart after IAM drift would crash-loop the whole app, and a rollback cannot fix drift. The only boot-time network call is a credential check that an enabled plugin declares: one cheap read-only call through its adapter, one attempt, bounded timeout. UNAUTHORIZED, PERMANENT_ERROR or NOT_FOUND logs ERROR credential_check_failed; TRANSIENT_ERROR logs WARNING credential_check_inconclusive. Neither aborts, and the feature stays registered and recovers without a restart once the credential is fixed. The existing error and warning alarms are the alert path. svcs pings stay diagnostics. Worked example: someone removes the access-sync role; the app, incidents included, keeps serving through any restart, access sync returns UNAUTHORIZED, and the error alarm fires.
2. /health and /version stay static and serve as both liveness and readiness. No deep or dependency check stands behind the Dockerfile, ECS, ALB or Route53 checks. cloud-portability.md's 'readiness probe green' is that endpoint.
3. Plugin boot failure is fixed by layer and kind, with no per-plugin override: an import error or a raising hookimpl aborts in every layer; an invalid settings slice skips a feature (CRITICAL plugin_boot_failed) and aborts for a capability or host service; a credential failure alerts and never aborts (TASK-126). Backstage's per-plugin onPluginBootFailure switch was considered and rejected, so no feature can opt into taking the whole app down.
4. Feature-conditional required settings are validated only when the plugin is enabled (TASK-112), statically. access/request's fallback-approver validator is the pattern.

SPLIT OUT: vendor dependency monitoring (metrics and alarms, active probes, the four integration_healthchecks entries, the unused provider health_check methods, the no-cheap-probe case) moved to TASK-127. The SSM parameter inventory moved to TASK-111 AC. Route53 stays with TASK-68.

AMENDED RECORDS: lifecycle.md, dependency-injection.md, plugins.md, configuration.md, outbound-clients.md, health-checks.md, cloud-portability.md, observability.md.
FOLLOW-UPS: TASK-98 (rescoped: lazy AssumeRole, fixes the boot crash), TASK-126 (feature isolation and credential checks), TASK-127 (vendor monitoring decision), TASK-128 (remove the directory boot warmup). Updated: TASK-109, TASK-110, TASK-24, TASK-53, TASK-111, TASK-64, TASK-25.5, TASK-25.6, TASK-89, TASK-112, TASK-68.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 decisions/health-checks.md states that every platform health check is static and serves as liveness and readiness, and cloud-portability.md's readiness contract points to it
- [x] #2 decisions/outbound-clients.md records that factories do no network I/O and assumed-role credentials are deferred and refreshable, and lists eager AssumeRole as a tolerated divergence under TASK-98
- [x] #3 Every amended record cites current web sources, has mechanically verifiable Checks and a dated Changes line, and no other record in decisions/ contradicts them (cascade grep)
- [x] #4 Follow-up tasks exist (TASK-98 rescoped, TASK-126, TASK-127, TASK-128) and the dependent tasks whose wording conflicted are updated through the CLI; no production code changed
- [x] #5 decisions/plugins.md, configuration.md and lifecycle.md record the fixed boot-failure policy (code defects abort; a feature with invalid settings is skipped; credential failures alert without aborting) with Checks; observability.md sets plugin_boot_failed at CRITICAL and credential_check_failed at ERROR on the existing error alarm
- [x] #6 decisions/lifecycle.md and dependency-injection.md state that construction and settings validation make no network call, and that the only boot-time network call is a declared, classified credential check that alerts and never aborts, with boot tests for both outcomes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25: decision records amended in place (lifecycle, dependency-injection, plugins, configuration, outbound-clients, health-checks, cloud-portability, observability; README index scopes). Cascade grep over decisions/ for 'is fatal|aborts boot|warm|health check|readiness|eager' found no contradicting record; security.md's JWKS fail-degraded rule and static 'fails boot' checks are consistent. All amended records stay under 150 lines with the four frontmatter fields. Sources verified 2026-09-25: ECS circuit breaker, ALB target-group health checks, Kubernetes probes, AWS Builders' Library health checks, svcs health checks, Backstage backend startup onPluginBootFailure. uvicorn lifespan-before-listen and botocore DeferredRefreshableCredentials/AssumeRoleCredentialFetcher checked in the installed packages (botocore 1.42.54). No production code changed. Awaiting human review before Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 18:57
---
FIELD EVIDENCE 2026-09-17, investigation complete (reproduced and instrumented on main @ 27fb2bda). Supersedes the first draft of this comment, which left the other warmups untraced. AC#1's "eager AssumeRole in get_aws_client" is not hypothetical: it already fails boot, and this comment records the full boot-time network-I/O inventory it belongs to.

1. METHOD. Each candidate was run with AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN / AWS_PROFILE unset, under a socket.socket.connect spy that counts and names every outbound connection. So "net=0" below means no network I/O was attempted, not that it happened to succeed.

2. BOOT-TIME NETWORK I/O INVENTORY (complete, measured)
   jwks_manager.warmup()            net=0   -> ok
   get_directory_provider()         net=0   -> ok  (construction is lazy)
   directory_provider.warmup()      net=2   -> ok  (admin.googleapis.com, oauth2.googleapis.com)
   get_aws_client("dynamodb")       net=0   -> ok  (no role ARN: lazy boto3.Session)
   get_aws_client("identitystore", role_arn=...)  net=1  -> ClientError InvalidClientTokenId
   startup_warmup: oncall_sync      net=0   -> ok
   startup_warmup: access.catalog   net=0   -> ok
   startup_warmup: access.request   net=0   -> ValidationError (static settings validation)
   startup_warmup: access.sync      net=1   -> ClientError InvalidClientTokenId

3. CORRECTION TO THIS TASK'S OWN DESCRIPTION. The "Network I/O at boot today" bullet lists "server/lifespan.py:153 jwks_manager.warmup() (unconditional)". That is WRONG: JWKSManager.warmup (infrastructure/security/jwks.py:103-119) only constructs PyJWKClient objects, and its docstring says so explicitly -- "Keys are not fetched from the JWKS URI here; that happens on the first token validation." Measured net=0. JWKS is already lazy-on-first-use and is NOT a boot dependency. The inventory in the description should be corrected to two entries, not three: the directory warmup and the eager AssumeRole.

4. THE ONLY FATAL VENDOR CALL AT BOOT. Of the four startup_warmup hookimpls, exactly one performs network I/O: packages/access/sync. Chain:
   server/lifespan.py:188 auto_discover_plugins(pm, base_paths=["packages", "modules"])
   -> packages/access/sync/__init__.py:83 startup_warmup -> get_access_sync_coordinator()
   -> packages/access/sync/providers.py:64 -> :38 build_aws_identity_center_adapter()
   -> packages/access/sync/adapters/aws_identity_center.py:1226 get_aws_client("identitystore", role_arn=...)
   -> integrations/aws/client.py:154 _session_for -> :181 -> :192 sts.assume_role(...)
   botocore.exceptions.ClientError: An error occurred (InvalidClientTokenId) when calling the AssumeRole operation: The security token included in the request is invalid.
   "import main" alone succeeds, so this is a lifespan failure, not an import-time one.

5. WHY IT IS FATAL. get_aws_client's docstring (client.py:147-149) states role_arn "assumes that role eagerly through STS before the client is built" -- a live network call at CONSTRUCTION, not first use. packages/access/sync/__init__.py:63-64 states the counterpart rule: "For enabled paths, startup failures are fatal and must propagate so misconfiguration is detected before traffic." Together they make AWS STS a hard boot dependency of the whole service, on behalf of one feature adapter.

6. TRIGGER CONDITIONS (all three required; this is why it looks intermittent)
   a. ACCESS_SYNC_ENABLED=true -- defaults to false; set in the developer .env.
   b. AWS_ORG_ACCOUNT_ROLE_ARN non-empty -- integrations/aws/settings.py:107 defaults to "", mapped by SERVICE_ROLE_MAP["identitystore"] (:118); aws_identity_center.py:1225 does "... or None", so an empty ARN skips AssumeRole and boot survives. The devcontainer environment exports this variable.
   c. No valid ambient AWS credentials.

7. PRODUCTION POSTURE -- CORRECTED 2026-09-17 (the first version of this paragraph was WRONG and its conclusion is withdrawn). It claimed production boots with access sync disabled because terraform/templates/sre-bot.json.tpl supplies only four environment variables and terraform/ssm.tf holds only the GCP key. The ECS task definition is NOT the only configuration source. app/bin/entry.sh:3-4 runs, at container start:
     aws ssm get-parameter --name sre-bot-config            ... > ".env"
     aws ssm get-parameter --name sre-bot-config-infrastructure ... >> ".env"
   so the real production configuration is the concatenation of two SSM parameters written into .env before uvicorn starts. terraform/iam.tf:32-33 grants read access to exactly those two parameter ARNs, but terraform/ssm.tf manages only gcp_sre_service_account_key -- their CONTENTS are not in version control and cannot be determined from this repository. app/packages/access/sync/README.md:76 confirms the intended workflow: "Add these vars to the sre-bot-config (or sre-bot-config-infrastructure) SSM parameter alongside the other app config."
   CONSEQUENCE: whether production currently sets ACCESS_SYNC_ENABLED and AWS_ORG_ACCOUNT_ROLE_ARN is UNKNOWN from the repo, so this task must not assume the boot-time AssumeRole is dormant in production. Someone with SSM read access should check both parameters and record the answer here; that is the difference between a latent risk and a live one. The same uncertainty applies to DIRECTORY_REQUIRE_STARTUP_WARMUP and SLACK_ENABLED (which also defaults to false yet plainly must be true in production -- direct evidence that the SSM bundle carries feature flags).

8. THE ASYMMETRY THAT IS THE ACTUAL DESIGN GAP. The Google directory path already implements the pattern this task is being asked to decide: infrastructure/directory/settings.py:41 DIRECTORY_REQUIRE_STARTUP_WARMUP defaults to FALSE and is described as "Opt in to fail-fast startup validation against the remote directory"; lifespan.py:171-177 honours it and logs directory_provider_warmup_skipped otherwise. The AWS path has NO equivalent switch: whenever the feature is on and a role ARN is set, boot performs STS I/O unconditionally, with no opt-out and no timeout setting (the directory path even has DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS). Two capabilities, two opposite postures, neither recorded as a decision. AC#1 and AC#5 should resolve this asymmetry explicitly rather than treat the AWS case alone.

9. THE GOOD CONTRAST FOR AC#1's "conditional required settings". packages/access/request's warmup failed with a pydantic ValidationError -- "ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG must be set when ACCESS_REQUESTS is enabled" -- at net=0. That is exactly the researched target behaviour: enabling a feature without its required configuration crashes fast on STATIC validation, with no network call. access/sync is the counter-example. Both are worth naming in the decision record as the wanted and unwanted shapes.

10. PRIOR WORKAROUND ALREADY IN THE TREE. app/pyproject.toml:107-111 pins "ACCESS_SYNC_ENABLED=false" for the test suite, commented: "Feature warmups must not depend on the developer's .env: tests that need a feature enable it explicitly. ACCESS_SYNC_ENABLED=true would make lifespan build the AWS Identity Center adapter (and assume its role) at startup." The test suite has already had to neutralize this; local dev has not.

11. INTERACTION WITH TASK-29 (already a dependent of this task). TASK-29 step 2 proposes that "Lifespan phase 2 invokes every registered provider - construction and settings validation at boot, fail fast (a poisoned provider aborts before yield)". Applied to the current factory, that would turn EVERY role-bearing provider into a boot-time AssumeRole, generalizing today's single failure across the whole provider set. This task's AC#1 must settle the eager-AssumeRole question before TASK-29 is planned; the dependency is already wired.

12. NEW GAP FOUND AND TRACKED SEPARATELY: TASK-98. Eager AssumeRole is not only a boot problem. No build_*_adapter() is cached, and client.py:7-9 states the design intent -- "Clients are built per call and never cached, so assumed credentials never need refreshing" -- so every call site pays a fresh STS round-trip, measured at one new STS connection per build across repeated calls. Builders that construct both a retrying and a retries-disabled client double it (identity_center.py:304-305, dynamodb.py:132-133). modules/aws/ops_group_assignment.py:24/:49/:63 makes four AssumeRole calls in one flow; jobs/scheduled_tasks.py:127 makes two every five minutes for a log-only probe. Only SERVICE_ROLE_MAP services with a non-empty ARN are affected -- dynamodb has no entry, which is why storage and idempotency are unaffected. That is a runtime latency and STS-throttling concern rather than a health-model one, so it was raised as TASK-98 (depends on this task) instead of being folded in here. TASK-98 must not contradict AC#1's outcome.

13. RELATED TASKS CHECKED. TASK-89 (spike, To Do) owns the other half of this seam -- whether eager AssumeRole and the role-ARN settings survive hosting outside AWS -- and has been updated with the same evidence; its AC#1 and this task's AC#1 must not diverge on get_aws_client, and no dependency is wired between them (left for the human). TASK-25.2.6 already owns retiring the duplicate AWS settings home (infrastructure/configuration/integrations/aws.py vs integrations/aws/settings.py, both aliasing AWS_ORG_ACCOUNT_ROLE_ARN) and already anticipates that "decisions/outbound-clients.md gets at most one short dated sentence if the eager AssumeRole choice needs recording" -- that sentence should follow this task's decision, not precede it. TASK-68 (Route53 health check) is the other existing dependent.

Nothing from the original investigation list remains untraced: all four startup_warmup hookimpls, both provider warmups, the JWKS path and both get_aws_client shapes were measured directly.
---

created: 2026-09-17 19:22
---
SCOPE DECISION 2026-09-17 (human): the untracked-production-configuration gap found while investigating the boot crash has no task of its own and is NOT given one. AC#2 was widened instead, because "which mechanism gates feature enablement" and "where those flags are actually set" are the same question, and AC#9 already produces the follow-up tasks.

AC#2 now additionally covers: the sre-bot-config / sre-bot-config-infrastructure SSM bundle as the real production configuration source (app/bin/entry.sh:3-4), the fact that terraform reads but does not manage it (terraform/iam.tf:32-33 vs terraform/ssm.tf), and the per-feature enablement procedure documented at app/packages/access/sync/README.md:76. Scope is RECORD AND DOCUMENT ONLY; migrating the bundle to a managed, reviewable channel is explicitly deferred to a follow-up under AC#9.

This also supersedes the open action in section 7 of the field-evidence comment: reading the two SSM parameters and recording whether ACCESS_SYNC_ENABLED, AWS_ORG_ACCOUNT_ROLE_ARN and DIRECTORY_REQUIRE_STARTUP_WARMUP are set in production is now AC#2 work, not a loose note. Until it is done, AC#1 must treat the boot-time AssumeRole as possibly live in production rather than dormant.

No other feature was found to need separate tracking: every feature's settings flow through the same two SSM parameters, so this is one gap, not one per package. Access sync is simply the first feature whose enablement is blocked by it.
---

created: 2026-09-24 20:10
---
2026-09-24 alignment: two questions this record was to answer are now decided. (1) Startup validation and where warmup belongs: decisions/dependency-injection.md and lifecycle.md phase 2 resolve every registered core service once from a startup container and run its health check before yield; per-feature startup_warmup hookimpls and lru_cache providers are the pattern being replaced (TASK-109, which depends on this task). (2) Plugin enablement moves to checked-in configuration files (TASK-112). Remaining open: liveness vs readiness semantics, which dependency checks a boot health check may call (for example eager AssumeRole) versus runtime vendor monitoring, and the Route53/ALB layering (TASK-68). References to decisions/layers.md read as decisions/plugin-architecture.md.
---
<!-- COMMENTS:END -->
