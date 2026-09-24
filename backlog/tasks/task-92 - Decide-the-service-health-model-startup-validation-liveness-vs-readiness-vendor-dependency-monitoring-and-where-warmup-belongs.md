---
id: TASK-92
title: >-
  Decide the service health model: startup validation, liveness vs readiness,
  vendor dependency monitoring, and where warmup belongs
status: To Do
assignee: []
created_date: '2026-09-14 14:55'
updated_date: '2026-09-24 20:10'
labels:
  - architecture
  - clients
  - observability
milestone: m-4
dependencies: []
references:
  - decisions/health-checks.md
  - decisions/configuration.md
  - decisions/dependency-injection.md
  - decisions/lifecycle.md
  - decisions/cloud-portability.md
  - decisions/plugins.md
  - decisions/observability.md
  - decisions/outbound-clients.md
  - decisions/security.md
  - app/jobs/scheduled_tasks.py
  - app/server/lifespan.py
  - app/api/routes/system.py
  - app/integrations/aws/client.py
  - app/integrations/slack/settings.py
  - app/infrastructure/directory/provider.py
  - app/infrastructure/drive/provider.py
  - terraform/alb.tf
  - terraform/route53.tf
  - terraform/templates/sre-bot.json.tpl
  - decisions/plugin-architecture.md
priority: medium
ordinal: 199000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ANALYSIS + DECISION-RECORD TASK (no production code). Created 2026-09-14 by human decision while planning TASK-25.2.3.2.4. It ABSORBS TASK-82 (archived), whose full question and evidence are carried below. Follow-up implementation tasks are created only after the decision is approved.

WHY: while planning the aws healthcheck flip, the legacy identity_store healthcheck treated an empty store as unhealthy and the new adapter treats it as healthy. That raised the underlying question: what are health checks for, when should they be used, and what is our gap? Three concerns lack a coherent, recorded model:
(A) Startup validation: fail fast when a required setting is missing, conditional on which features/integrations are enabled.
(B) Our own service health: what the Dockerfile HEALTHCHECK, ECS task-definition healthCheck, ALB target group and Route53 checks hit, and whether any readiness/deep check exists.
(C) Third-party vendor health: whether periodic SDK "healthcheck" calls are good practice, what "healthy" means, and what signal and alarm replace or complement them.

CURRENT STATE (grep-verified 2026-09-14):
- B: /health and /version (app/api/routes/system.py:13,20) are static, with no dependency calls. Dockerfile HEALTHCHECK and ECS healthCheck (terraform/templates/sre-bot.json.tpl:20-28) hit /health; the ALB (terraform/alb.tf:10-17) and Route53 (terraform/route53.tf:21-32, unwired, TASK-68) hit /version. decisions/health-checks.md covers only these layers.
- C: jobs/scheduled_tasks.py:121-145 integration_healthchecks runs every 5 minutes over google_drive (reads the incident template metadata), maxmind (test lookup of 8.8.8.8), opsgenie (GET /v1/services) and aws (identity store ListUsers; moved onto IdentityCenterAdapter.healthcheck by TASK-25.2.3.2.4, which also guards the loop so a raising check logs unhealthy). Results are logs only: no metric, alarm or notification consumes them (repo-wide rg incl. terraform). No decision record covers vendor probing, and decisions/observability.md has no metrics/alarm decision.
- A: pydantic-settings slices; SlackSettings (app/integrations/slack/settings.py:37-55) already requires tokens only when SLACK_ENABLED, via a validator; packages/access has ACCESS_*_ENABLED flags. decisions/configuration.md:28 says a missing required credential fails boot during lifespan phase 2, but providers are still lazy lru_cache (TASK-29 not done). decisions/plugins.md:42 says feature flags block plugins via pm.set_blocked driven by settings, but set_blocked is not called anywhere in app/.
- Network I/O at boot today: server/lifespan.py:153 jwks_manager.warmup() (unconditional); :172 directory_provider.warmup() (gated on require_startup_warmup, raises RuntimeError); :220 translation_service.health_check() (local). integrations/aws/client.py get_aws_client performs eager STS AssumeRole during construction.

CARRIED FROM TASK-82 (grep-verified 2026-09-09):
- DirectoryProvider and DriveProvider both declare warmup() and health_check(). DirectoryProvider.warmup() has real callers (server/lifespan.py:172; modules/dev/google.py:55, a diagnostic Slack command). DriveProvider.warmup(), DriveProvider.health_check() and DirectoryProvider.health_check() have ZERO production callers. GoogleDriveProvider.health_check() returns OperationResult.success unconditionally, so it is not a liveness check. The Sheets capability (TASK-25.1.6.10.2) dropped both methods because the Sheets API has no cheap probe endpoint without a spreadsheet id.
- decisions/dependency-injection.md's eager composition means lifespan phase 2 INVOKES every registered provider (construction + validation), not a warmup() method on each capability contract. outbound-clients.md puts authenticated client construction in integrations/<vendor>/.
- TASK-82's question: should connectivity warmup/liveness be (a) a per-capability Protocol method, (b) a concern of the vendor client factory invoked at startup, (c) part of the DI registry's eager phase-2 invocation with no capability method, or (d) a mix keyed on whether a cheap probe exists.

DISCREPANCIES TO RESOLVE (do not assume; raise to the human):
1. dependency-injection.md:28 / lifecycle.md:19 eager phase-2 construction vs network I/O at boot: eager AssumeRole, JWKS warmup and directory warmup make vendors or the IdP hard dependencies of a deploy. Research advises static-only startup validation. TASK-82 option (b) and TASK-29's wording would add more. security.md already requires JWKS to be fail-degraded at runtime.
2. cloud-portability.md:25 says "deploy success = readiness probe green", but no readiness probe is defined, and the research advises against deep readiness checks behind the ALB/ECS.
3. plugins.md:42 pm.set_blocked feature flags (unimplemented) vs per-slice *_ENABLED settings: two feature-enablement mechanisms. This is the input for conditional required-settings validation.
4. No record decides dependency metrics/alarms (CloudWatch EMF vs OpenTelemetry) or whether the log-only integration_healthchecks job should exist.
5. The meaning of "healthy" for a vendor probe (authn/authz + reachability vs data semantics, e.g. empty identity store).

RESEARCH SUMMARY (2026-09-14; re-verify sources per the architecture agent's refresh rule):
- Keep load-balancer and container checks shallow. A dependency check in them turns the dependency into a hard dependency, and a shared vendor failure marks the whole fleet unhealthy; the ALB fails open when all targets are unhealthy. AWS Builders' Library "Implementing health checks" (https://d1.awsstatic.com/builderslibrary/pdfs/implementing-health-checks.pdf); ALB (https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html); ECS health checks (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html); the ECS deployment circuit breaker counts ELB/container health failures and rolls back (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html). Contested: Kubernetes allows backend checks in readiness (https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/).
- Startup: validate presence/shape with pydantic-settings (https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/), required only for enabled features. Crash rather than start degraded (the ECS circuit breaker rolls back a bad config). No network/credential probes at boot; local resources such as the MaxMind DB file are the exception.
- Vendor monitoring: a monitor without an alarm is a Well-Architected anti-pattern (https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_withstand_component_failures_monitoring_health.html). Prefer passive per-dependency RED metrics derived from adapter OperationResult (https://sre.google/sre-book/monitoring-distributed-systems/) emitted via EMF (https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html) or OTel, with low-cardinality vendor/operation/outcome dimensions. Justify an active probe only for low-traffic integrations or credential-expiry detection (https://sre.google/workbook/alerting-on-slos/). If allowed: one scheduled read-only call that tests authn/authz + reachability (empty data = healthy), mapped from OperationResult (unauthorized/permanent -> page; transient -> alarm only when sustained), emitting a metric, and with scoped IAM. Optional: an authenticated operator diagnostics endpoint returning cached state, never used by the ALB (https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring). Note: Opsgenie end of support is 2027-04-05 (secondary sources), so do not invest in a new Opsgenie probe.

OUTPUT: amendments to decisions/health-checks.md, configuration.md, dependency-injection.md (and lifecycle.md, cloud-portability.md, plugins.md, observability.md where the decision touches them), or a new dependency-health record, each with a mechanically verifiable Checks section; then follow-up tasks.
NOT IN SCOPE: implementing any change. TASK-29 and TASK-68 depend on this decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Startup validation is decided and recorded in decisions/configuration.md: what is validated at boot (static presence/shape vs network or credential probes), how required settings are conditional on enabled features, and crash vs start-degraded; the eager phase-2 construction in dependency-injection.md and lifecycle.md is reconciled with that rule, explicitly covering eager AssumeRole in get_aws_client, jwks_manager.warmup and directory warmup
- [ ] #2 Feature enablement is reconciled: plugins.md's pm.set_blocked mechanism (not implemented) vs per-slice *_ENABLED settings flags, stating which one gates plugin registration and conditional settings validation Because *_ENABLED flags default to false in code, the decision must also state WHERE they are set in the deployment: production configuration is the concatenation of the sre-bot-config and sre-bot-config-infrastructure SSM parameters, fetched by app/bin/entry.sh:3-4 into .env at container start; terraform/iam.tf:32-33 grants read on those two ARNs while terraform/ssm.tf manages only gcp_sre_service_account_key, so their contents are unversioned, unreviewed and not discoverable from the repo (app/packages/access/sync/README.md:76 documents the manual edit as the enablement procedure). Scope here is RECORD AND DOCUMENT ONLY (human decision 2026-09-17): capture what the two parameters actually contain today, document the per-feature enablement procedure, and state the drift risk. Migrating the bundle to a managed channel is explicitly NOT decided here and belongs to a follow-up under AC#9. Answering this also resolves the open question left in the field-evidence comment: whether production currently sets ACCESS_SYNC_ENABLED, AWS_ORG_ACCOUNT_ROLE_ARN and DIRECTORY_REQUIRE_STARTUP_WARMUP, which decides whether the boot-time AssumeRole in AC#1 is a latent or a live production risk.
- [ ] #3 Service health is decided and recorded in decisions/health-checks.md: what the Dockerfile, ECS, ALB and Route53 checks hit and return, whether any readiness or deep dependency check exists, and cloud-portability.md's 'readiness probe green' deploy contract is reconciled with it
- [ ] #4 Vendor dependency health is decided and recorded (a new record or an amendment, plus a metrics/alarm decision in observability.md): whether periodic SDK probes are allowed and under which criteria, what healthy means (with the empty identity store as the worked example), the passive per-dependency signal and its alarms, and the fate of each of the four integration_healthchecks entries in jobs/scheduled_tasks.py
- [ ] #5 A written decision states where connectivity warmup and liveness belong (vendor client factory, DI provider registry, capability Protocol, or a keyed mix) with the alternatives and tradeoffs recorded
- [ ] #6 The unused DriveProvider.warmup/health_check, DirectoryProvider.health_check and the unconditionally-successful GoogleDriveProvider.health_check are explicitly addressed by the decision (kept with a stated purpose, or scheduled for removal via follow-up tasks)
- [ ] #7 The decision states what a capability should do when its vendor surface offers no cheap probe endpoint, using Google Sheets as the worked example
- [ ] #8 Every amended or new decision record cites current web sources and has a mechanically verifiable Checks section; TASK-29 and TASK-68 are reviewed against the decision and updated through the CLI where their wording conflicts
- [ ] #9 Follow-up implementation tasks are created with dependencies on this task; no production code is changed by this task
<!-- AC:END -->

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
