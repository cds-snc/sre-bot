# ADR-0081: CI/CD Pipeline and Deployment Validation

---
adr_id: ADR-0081
title: "CI/CD Pipeline and Deployment Validation"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: infrastructure
primary_domain: "Delivery and Environment Parity"
secondary_domains:

- "Testing and Quality Gates"
- "Observability and Operations"
owners:
- SRE Team
date_created: 2026-05-01
last_updated: 2026-05-01
last_reviewed: 2026-05-01
next_review_due: 2026-08-29
constrained_by:
- ADR-0044
- ADR-0080
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
- ADR-0052
- ADR-0054
- ADR-0062
- ADR-0064
related_packages: []

---

## Context

### Problem statement

The CI/CD pipeline infrastructure lacks a governing ADR. ADR-0052 (Build-Release-Run Delivery Standard) defines the application-side lifecycle model — immutable build artifacts, release-phase configuration binding, and run-phase constraints — but does not govern the pipeline infrastructure that enforces those contracts. Specifically:

1. **No deployment validation standard.** The current deployment pipeline (`build_and_deploy.yml`) uses `aws ecs wait services-stable` with `continue-on-error: true`, meaning deployment failures are advisory. No endpoint health check verifies the deployed application is serving traffic correctly. No automatic rollback occurs on failure.

2. **CI gates enforced but not codified.** Core CI gates (lint, format, unit/integration tests, container build) are blocking — PRs cannot merge unless all pass. SAST is enforced via Bandit (`bandit_security_scan.yml`, high-severity findings on `**/*.py`, blocking), and dependency vulnerability scanning is provided continuously by Renovate bot (centrally managed via `cds-snc/renovate-config`). However, type checking (`mypy`) intentionally runs with `|| true` because the legacy codebase is not yet fully type-compliant; enforcing it now would block all development. No ADR codifies which gates are mandatory vs. deferred, nor captures the current Bandit configuration's review debt.

3. **IaC validation exists but apply-side gaps remain.** The `cds-snc/terraform-plan` GitHub Action (a centrally managed organizational action) already runs `terraform init`, `terraform validate`, `terraform fmt -check`, `terraform plan`, and Conftest policy checks on PRs, posting plan output as PR comments. This is a required status check. However, `tf_apply.yml` re-runs `terragrunt apply --auto-approve` on merge rather than applying the reviewed plan artifact, creating a window for state drift between plan review and apply.

4. **No deployment concurrency control.** Multiple deployments to the same ECS service can run concurrently, creating race conditions between `force-new-deployment` calls.

### Business/operational drivers

- **Reliability:** DORA research demonstrates that deployment validation and automated rollback directly correlate with lower change failure rates and faster failed deployment recovery times. The current pipeline has a 15-minute blind spot between deployment and stability confirmation.
- **Security posture:** SAST (Bandit) and dependency vulnerability scanning (Renovate) exist but are not governed by an ADR. The Bandit workflow and its configuration are due for review and update. Container image scanning runs as a separate workflow (`docker_vulnerability_scan.yml`), not integrated into the build-and-deploy pipeline.
- **ADR-0052 compliance:** The build-release-run model requires that deployed releases be verifiable. Without deployment validation, ADR-0052's requirement that deployed release identity (image digest/SHA) be visible in startup logs has no automated enforcement.
- **ADR-0080 boundary:** This ADR governs infrastructure-domain concerns (CI/CD pipelines, deployment orchestration, IaC validation). Application-domain testing standards remain governed by ADR-0062.

### Constraints

- Pipeline infrastructure is GitHub Actions + AWS ECS (rolling deployment). Blue/green or canary strategies are out of scope for current capacity.
- ECS deployment circuit breaker provides built-in failure detection with automatic rollback — it is the platform-native mechanism for deployment validation.
- All pipeline changes must be implementable incrementally. Standards that require new infrastructure (e.g., staging environments, load testing clusters) are marked as aspirational targets.

### Non-goals

- Application-level test strategy (governed by ADR-0062).
- Application-level quality gate tool selection — e.g., which linter, formatter, or type checker to use (governed by existing application ADRs).
- Smoke test or end-to-end test framework selection (deferred to a Tier-4 decision).
- Multi-environment promotion (staging → production) — deferred until operational need is demonstrated.

## Decision

### Chosen approach

Establish mandatory CI/CD pipeline quality standards across three pipeline stages: **pre-merge CI**, **deployment execution**, and **infrastructure-as-code management**. Each stage defines blocking gates that must pass before the pipeline proceeds to the next stage. The standards enforce deployment validation, failure recovery, and security scanning as infrastructure-domain requirements.

### Why this approach

1. **Contract-based.** ADR-0080 P2 (Contract-Based Interface) requires that infrastructure ADRs define how hosting platforms fulfill application contracts. This ADR defines the pipeline-side fulfillment of ADR-0052's build-release-run model and ADR-0062's testing mandate.
2. **Platform-aware, not platform-locked.** Standards reference deployment validation concepts (circuit breaker, health check, rollback) rather than AWS-specific APIs. The ECS-specific fulfillment is documented in the Compliance section as the current hosting platform implementation.
3. **Incrementally adoptable.** Standards are classified as **mandatory** (must be enforced now) or **target** (must be implemented by a specified date). This prevents the ADR from blocking progress while establishing clear expectations.

## Standards

### S1 — Pre-Merge CI Quality Gates

All of the following gates must be **blocking** — a failure in any gate must prevent merge to the default branch:

| Gate | Requirement | Classification | Current State |
|------|-------------|----------------|---------------|
| **Lint** | Static analysis must pass with zero violations | Mandatory | ✅ Enforced (flake8, blocking) |
| **Format** | Code formatting check must pass | Mandatory | ✅ Enforced (black --check, blocking) |
| **Type check** | Static type checking must pass (not soft-fail) | Target | ⚠️ Runs but soft-fail (`|| true`) — legacy code non-compliant |
| **Unit and integration tests** | All tests in the CI test suite must pass | Mandatory | ✅ Enforced (pytest, blocking) |
| **SAST** | Static application security testing must pass | Mandatory | ✅ Enforced (Bandit, high-severity, blocking) — ⚠️ config due for review |
| **Dependency vulnerability scan** | Known-vulnerable dependencies must be remediated | Mandatory | ✅ Enforced (Renovate bot, continuous, centrally managed) |
| **Container build** | Container image must build successfully on PRs | Mandatory | ✅ Enforced (ci_container.yml, blocking) |

**Rationale:** A quality gate that can be bypassed provides no assurance. The `|| true` anti-pattern — running a tool but ignoring its exit code — must not be used for any mandatory gate. For type checking specifically, enforcement is deferred until the application codebase achieves full type compliance through the ongoing refactoring effort. When that milestone is reached, type checking must transition from Target to Mandatory.

### S2 — Deployment Artifact Integrity

Before a deployment artifact is pushed to the container registry:

1. The artifact must be tagged with an immutable identifier (git SHA + build date).
2. The `:latest` tag may be applied for convenience but must not be the sole deployment reference.
3. Container image scanning (vulnerability detection) must run against the built image before push. Critical or high-severity vulnerabilities must block the push.

**Classification:** Items 1–2 are mandatory. Item 3 is a target.

### S3 — Deployment Validation Gate

After initiating a deployment, the pipeline must verify deployment success before declaring completion:

1. **Deployment failure detection must be enabled.** The deployment orchestrator must detect task launch failures and health check failures automatically. Failed deployments must trigger automatic rollback to the last successful deployment.
2. **Health check verification is required.** The deployment must not be declared successful based solely on task count stability. At minimum, the deployment orchestrator's built-in health checks (load balancer target group health, container health checks) must be configured and passing.
3. **Deployment wait must be blocking.** The pipeline step that waits for deployment stability must not use `continue-on-error` or equivalent soft-failure patterns. A failed deployment must fail the pipeline.

**Classification:** All items are mandatory.

### S4 — Deployment Failure Notification

1. Deployment outcomes (success or failure) must be reported to the team's operational notification channel.
2. Failure notifications must include: the deployment identifier (git SHA), the failure stage (build, push, deploy, validation), and a link to the pipeline run.
3. Deployment metadata must be reported to the organization's security and observability platform (e.g., Sentinel deployment log).

**Classification:** Items 1–2 are mandatory. Item 3 is mandatory (already implemented).

### S5 — Deployment Concurrency Control

1. Only one deployment to a given service may be in progress at a time. Concurrent deployment attempts must be serialized or the newer attempt must cancel the in-progress deployment.
2. The pipeline must use a concurrency control mechanism (e.g., GitHub Actions `concurrency` groups) to enforce this constraint.

**Classification:** Mandatory.

### S6 — Infrastructure-as-Code Validation

Terraform (or equivalent IaC) changes must pass the following gates:

| Gate | Stage | Requirement | Classification | Current State |
|------|-------|-------------|----------------|---------------|
| **Format** | Pre-merge | `terraform fmt -check` must pass | Mandatory | ✅ Enforced via `cds-snc/terraform-plan` |
| **Validate** | Pre-merge | `terraform validate` must pass | Mandatory | ✅ Enforced via `cds-snc/terraform-plan` |
| **Policy checks** | Pre-merge | Conftest policy checks must pass | Mandatory | ✅ Enforced via `cds-snc/terraform-plan` |
| **Plan review** | Pre-merge | Plan output must be available for review on the PR | Mandatory | ✅ Enforced via `cds-snc/terraform-plan` (PR comment) |
| **Plan-artifact apply** | Merge | Apply must use the reviewed plan artifact, not re-plan | Target | ❌ `tf_apply.yml` re-plans and auto-approves |
| **Drift detection** | Scheduled | Periodic plan to detect configuration drift | Target | ❌ Not configured (action supports it) |

**Rationale:** IaC changes have blast radius equivalent to or greater than application code changes. The `cds-snc/terraform-plan` centrally managed action already provides comprehensive pre-merge validation including format, validate, plan, and Conftest policy checks. The remaining gap is on the apply side: `tf_apply.yml` re-runs `terragrunt apply --auto-approve` on merge, which creates a window where the applied plan may differ from the reviewed plan if infrastructure state changed between review and merge.

### S7 — Supply Chain Security

1. Software Bill of Materials (SBOM) generation must occur as part of the build pipeline, not post-deployment.
2. Dependency audit (known-vulnerable packages) must run in the pre-merge CI pipeline.

**Classification:** Target.

## Alternatives Considered

### 1. Extend ADR-0052 with pipeline standards

- **Pros:** Single ADR for all delivery concerns; avoids ADR proliferation.
- **Cons:** ADR-0052 is an application-domain ADR (governance_domain: application) governing the build-release-run model. Adding infrastructure pipeline enforcement standards would violate ADR-0080's governance domain separation. Pipeline infrastructure is replaceable independently of the application lifecycle model.
- **Why not chosen:** Governance domain violation. ADR-0052 defines *what* the application requires; this ADR defines *how* the pipeline infrastructure enforces it.

### 2. Defer to per-pipeline Tier-4 decisions

- **Pros:** Maximum flexibility; each pipeline can define its own validation requirements.
- **Cons:** No cross-cutting standard. Each pipeline would need to independently discover the same patterns (circuit breaker, health checks, concurrency control). Inconsistent validation quality across pipelines.
- **Why not chosen:** Tier-2 Standards exist to prevent per-feature reinvention. Deployment validation is a cross-cutting infrastructure concern.

### 3. Adopt blue/green or canary deployment strategy

- **Pros:** Superior deployment safety; enables progressive rollout and instant rollback.
- **Cons:** Requires significant infrastructure investment (dual target groups, traffic shifting, warm standby capacity). Current operational capacity does not justify the complexity for a single-service deployment.
- **Why not chosen:** Over-engineering for current scale. The rolling deployment model with circuit breaker provides adequate safety. This option remains available as a future evolution if scale or reliability requirements change.

## Compliance

### Current Hosting Platform: AWS ECS + GitHub Actions

The following table maps each standard to its concrete implementation on the current hosting platform.

| Standard | Current State | Remaining Gap |
|----------|---------------|---------------|
| S1 (CI gates) | Lint, format, tests, SAST (Bandit), container build all blocking on merge; dependency scanning via Renovate (continuous) | Type check deferred (legacy non-compliance); Bandit workflow and config due for review/update |
| S2 (Artifact integrity) | Immutable tags (SHA+date) implemented; no pre-push image scan | Integrate container image scanning before ECR push |
| S3 (Deployment validation) | `ecs wait services-stable` with `continue-on-error: true`; no circuit breaker | Enable ECS deployment circuit breaker with rollback; remove `continue-on-error`; configure ALB health checks |
| S4 (Failure notification) | Slack webhooks for success/failure; Sentinel deployment reporting | Enrich failure notifications with SHA and failure stage |
| S5 (Concurrency) | No concurrency control | Add GitHub Actions `concurrency` group to `build_and_deploy.yml` |
| S6 (IaC validation) | `cds-snc/terraform-plan` enforces fmt, validate, Conftest, plan review on PRs (blocking) | Plan-artifact apply (avoid re-plan on merge); drift detection |
| S7 (Supply chain) | SBOM generated post-deploy; container scan in separate workflow | Move SBOM to build stage; integrate dependency audit in CI |

### ECS Deployment Circuit Breaker

The ECS deployment circuit breaker is the platform-native mechanism for S3 compliance:

- **Stage 1:** Monitors tasks transitioning to `RUNNING` state. Consecutive failures increment the failure counter.
- **Stage 2:** Validates health checks (ALB target group, container health check, Cloud Map) for running tasks.
- **Rollback:** When the failure threshold is reached, the deployment is marked `FAILED` and automatically rolled back to the last `COMPLETED` deployment.
- **Threshold:** `min(max(3, ceil(0.5 * desired_count)), 200)`.

This must be enabled on the ECS service definition (Terraform `deployment_circuit_breaker` block with `enable = true` and `rollback = true`).

## Migration

### Implementation Priority

Standards are ordered by risk reduction and implementation complexity:

1. **S3 + S5** (deployment validation + concurrency) — highest risk reduction, moderate effort. Enable ECS circuit breaker in Terraform; add concurrency group to workflow; remove `continue-on-error`.
2. **S1** (CI gates) — review and update Bandit configuration; type check enforcement deferred until legacy refactoring completes.
3. **S6** (IaC validation) — implement plan-artifact apply to close the re-plan gap; configure drift detection.
4. **S4** (failure notification enrichment) — improve notification payload; low effort.
5. **S2 + S7** (artifact integrity + supply chain) — integrate image scanning and dependency audit; moderate effort.

### Coordination with Planned Migrations

The migration map includes two approved Tier-5 migrations that interact with this ADR's standards:

- **ADR-0068** (SSM-to-Release-Phase Migration, planned): When configuration binding moves from runtime SSM fetch to release-phase injection, the deployment validation gate (S3) will automatically verify that the new configuration produces a healthy deployment.
- **ADR-0069** (Port Binding Migration, planned): Port binding changes will be verified through the same deployment validation gate.

These ADRs are approved but not yet authored. When authored, they should reference ADR-0081 in their `related_records`.

## Risks

1. **False positive deployment failures.** ECS circuit breaker may trigger on transient health check failures (e.g., slow startup, dependency warmup). Mitigation: configure appropriate health check grace periods and deregistration delays on the ALB target group.
2. **CI pipeline duration increase.** Adding type checking, dependency scanning, and container image scanning will increase CI run time. Mitigation: parallelize CI stages; cache dependency scan results.
3. **Terraform plan artifact staleness.** If significant time passes between plan review and apply, the infrastructure state may have changed. Mitigation: implement plan artifact-based apply (target) to ensure the reviewed plan is what gets applied.

## References

- DORA Software Delivery Performance Metrics — change failure rate, failed deployment recovery time (<https://dora.dev/guides/dora-metrics-four-keys/>)
- AWS ECS Deployment Circuit Breaker — failure detection and automatic rollback (<https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html>)
- AWS ECS Rolling Deployment — minimumHealthyPercent, maximumPercent, image digest resolution (<https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html>)
- GitHub Actions Deployment — environments, concurrency groups, deployment protection rules (<https://docs.github.com/en/actions/use-cases-and-examples/deploying/deploying-with-github-actions>)
- Twelve-Factor App — Build, Release, Run (<https://12factor.net/build-release-run>)
- ADR-0052: Build-Release-Run Delivery Standard (application-side lifecycle model)
- ADR-0080: Application Portability Boundary (governance domain separation)
