---
id: TASK-92
title: >-
  Decide the service health model: startup validation, liveness vs readiness,
  vendor dependency monitoring, and where warmup belongs
status: To Do
assignee: []
created_date: '2026-09-14 14:55'
labels:
  - architecture
  - clients
  - observability
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
  - decisions/layers.md
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
- [ ] #2 Feature enablement is reconciled: plugins.md's pm.set_blocked mechanism (not implemented) vs per-slice *_ENABLED settings flags, stating which one gates plugin registration and conditional settings validation
- [ ] #3 Service health is decided and recorded in decisions/health-checks.md: what the Dockerfile, ECS, ALB and Route53 checks hit and return, whether any readiness or deep dependency check exists, and cloud-portability.md's 'readiness probe green' deploy contract is reconciled with it
- [ ] #4 Vendor dependency health is decided and recorded (a new record or an amendment, plus a metrics/alarm decision in observability.md): whether periodic SDK probes are allowed and under which criteria, what healthy means (with the empty identity store as the worked example), the passive per-dependency signal and its alarms, and the fate of each of the four integration_healthchecks entries in jobs/scheduled_tasks.py
- [ ] #5 A written decision states where connectivity warmup and liveness belong (vendor client factory, DI provider registry, capability Protocol, or a keyed mix) with the alternatives and tradeoffs recorded
- [ ] #6 The unused DriveProvider.warmup/health_check, DirectoryProvider.health_check and the unconditionally-successful GoogleDriveProvider.health_check are explicitly addressed by the decision (kept with a stated purpose, or scheduled for removal via follow-up tasks)
- [ ] #7 The decision states what a capability should do when its vendor surface offers no cheap probe endpoint, using Google Sheets as the worked example
- [ ] #8 Every amended or new decision record cites current web sources and has a mechanically verifiable Checks section; TASK-29 and TASK-68 are reviewed against the decision and updated through the CLI where their wording conflicts
- [ ] #9 Follow-up implementation tasks are created with dependencies on this task; no production code is changed by this task
<!-- AC:END -->
