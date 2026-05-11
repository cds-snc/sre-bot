---
title: "Build-Release-Run Pipeline"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [operations]
concerns: [cicd, compute]
constrained_by: [cloud-portability.md, environment-parity.md, configuration-ownership.md, port-binding-exposure.md, application-lifecycle.md, package-management.md, project-metadata.md, code-quality-tooling.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Build-Release-Run Pipeline

## Context and Problem Statement

Code reaches production through a sequence of stages: source on a developer's branch, source merged on `main`, a tested build artifact, that artifact deployed to a non-production environment, the same artifact deployed to production. Each stage transition has a potential for behaviour drift — a different image built for staging than was tested in CI, a release that injects configuration during the build instead of at run, a deploy that succeeds without the new task ever passing readiness, an environment promotion that re-builds the artifact instead of re-deploying the same one. Each drift opportunity is a place where "it worked in the previous stage" stops being predictive.

The problem this record addresses: **what is the standard pipeline for moving code to production — its build, release, and run stages, the boundary between them, the artifact identity, the promotion model, and the deploy-validation contract?** The answer determines:

1. Whether the artifact tested in CI is bit-for-bit the artifact that runs in production, or whether each environment rebuilds.
2. Whether environment-specific configuration is baked into a build (impossible to promote) or injected at release time (one build, many releases).
3. Whether a deploy is "verified" because the deploy command returned, or because the new task actually started, completed lifespan, and passed readiness.
4. Whether a failed deploy automatically returns to the previous good state, or whether a human operator has to intervene.
5. Whether the pipeline holds long-lived AWS credentials or authenticates per-run via short-lived federation.

**Constraints:**

- The application is a stateless container running on AWS ECS Fargate. Builds produce container images; releases combine an image with environment configuration; runs are tasks scheduled by the orchestrator.
- The same image is promoted across environments ([environment-parity.md](environment-parity.md)). Build and release are strictly separated; a "release" is an image plus per-environment configuration ([cloud-portability.md](cloud-portability.md), 12-factor V).
- All configuration is environment variables read at startup ([configuration-ownership.md](configuration-ownership.md)). The application does not fetch secrets at runtime from external stores; the deployment platform injects them as environment variables on the task definition. (A small set of secrets that *must* be fetched at runtime — e.g., a JWKS document refreshed periodically — are runtime *integrations*, not runtime *configuration*; they are distinct.)
- Lifespan completion (phase 6 reached, registries frozen) is the operational definition of "successfully started." Deploy validation must observe that signal, not just "task transitioned to RUNNING" ([application-lifecycle.md](application-lifecycle.md)).
- The Python interpreter version, the dependency lock, and the source tree are the same in CI as in the deployed image ([environment-parity.md](environment-parity.md)).
- The pipeline runs in GitHub Actions; the deployment target is AWS; secret access is by short-lived federation, not long-lived credentials.

**Non-goals:**

- This record does not own infrastructure provisioning (Terraform, IAM roles, ECR repository creation, ALB listener rules). Those are operations infrastructure managed in a separate codebase.
- This record does not pick the secret store (AWS Secrets Manager vs. Parameter Store) — those are configuration-platform decisions.
- This record does not specify per-feature acceptance criteria for promoting between environments. Those are feature-team concerns.
- This record does not own the developer's local-build path ([environment-parity.md](environment-parity.md) covers that).

## Considered Options

**Option 1 — One image per commit, identified by Git SHA; release combines the immutable image with per-environment configuration; deploy is a task-definition revision pointing at the SHA-tagged image; deploy validation reads the new task's `lifespan_started` log event with a bounded timeout; ECS deployment circuit breaker auto-rolls-back on health-check failure; GitHub Actions authenticates to AWS via OIDC.**

**Option 2 — Per-environment image builds.** Each environment has its own image, built from the same source with environment-specific build-args.

**Option 3 — Single mutable tag (`latest`) per environment.** Deploys repoint the tag; rollbacks repoint back.

**Option 4 — Long-lived AWS credentials in GitHub secrets.** GitHub Actions authenticates with `aws_access_key_id` / `aws_secret_access_key` stored as repository secrets.

## Decision Outcome

**Chosen: Option 1 — one image per commit, SHA-tagged; release = image + per-environment configuration; deploy validates lifespan completion; circuit breaker for auto-rollback; OIDC for AWS auth.**

This is the only option that delivers all five contract properties: bit-identical artifact across environments, configuration injected at release (not bake), deploy validation tied to lifespan completion (not a fuzzy "RUNNING" signal), automatic rollback on failure, and credential-free authentication for the pipeline. Per-environment builds (Option 2) re-introduce the dev/prod gap. Mutable tags (Option 3) make rollback ambiguous and historical state unrecoverable. Long-lived credentials (Option 4) is a concrete attack surface; OIDC is documented, free, and the canonical AWS pattern.

### Build

Builds are triggered on every push to `main`. The build stage is deterministic from source:

- **One image per commit.** The image is tagged with the commit SHA (`<repository>:<sha>`); a successful build produces exactly this tag. `latest` is not used.
- **Multi-stage Dockerfile.** A first stage installs build tools, exports the dependency lock, and builds the application; a final stage carries only the runtime artifacts. The final image contains no build tools, no compilers, no `pip` cache.
- **Same lock file.** The build installs from the same dependency lock that local development and CI use ([package-management.md](package-management.md)). The lock is committed to the repository; the build does not solve dependencies fresh.
- **Same Python version.** The Python minor version is declared once in project metadata and read by the Dockerfile, the local-development tooling, and CI ([project-metadata.md](project-metadata.md)).
- **No environment-specific build-args.** The Dockerfile does not accept `--build-arg ENVIRONMENT=...`. Two environments running the same SHA share bit-identical images.
- **Provenance.** The build records its source SHA, the build's timestamp, and the lock-file hash in a manifest stored alongside the image (e.g., as image labels). Operations can answer "what code is in this image" from the registry alone.

CI runs the linter, type checker, and test suites against the same source on the same Python version ([code-quality-tooling.md](code-quality-tooling.md), [testing-standards.md](testing-standards.md)). A failing CI step blocks the build; an image is only pushed after CI passes.

### Release

A release joins an immutable image with per-environment configuration:

- **One ECR repository per application; many tags per repository.** Tags include the commit SHA (immutable, primary identifier) and optionally a semantic-version tag for a Git-tagged release commit. Floating tags (`dev`, `staging`, `prod`) are convenience pointers used by tooling but are not the binding reference for any deploy — every deploy binds to the SHA tag explicitly, never a floating tag.
- **Configuration is injected at release.** The deployment platform creates a new task-definition revision that references the SHA-tagged image and the per-environment environment variables (and secret references, which the platform expands at task start). The task definition is the release artifact; it identifies the build (image SHA) and the configuration (env vars).
- **No runtime-only configuration fetch.** The application does not call out to a secret store on startup to retrieve missing settings. All required settings are present in the task definition at the moment the task starts ([cloud-portability.md](cloud-portability.md), [configuration-ownership.md](configuration-ownership.md)).
- **Releases are not rebuilds.** Promoting a SHA from staging to production creates a new task-definition revision (with the production environment's variables) referencing the same image. The image is not rebuilt for production.

### Run

The orchestrator (ECS) starts a task from a task-definition revision:

- The container's entrypoint launches uvicorn against the application's settings ([port-binding-exposure.md](port-binding-exposure.md)).
- Lifespan phases run; phase 6 (background) is gated by the canonical environment indicator ([environment-parity.md](environment-parity.md), [background-execution.md](background-execution.md)).
- The task emits its `lifespan_started` (or equivalent) structured log record on successful boot. This event carries the SHA, the task ARN, and the environment.
- The task serves traffic until it receives `SIGTERM`. The shutdown contract is the bounded timeline named in [port-binding-exposure.md](port-binding-exposure.md).

### Deploy validation

A deploy is "successful" when a new task has booted into readiness, not when an API call returned:

- **The deploy command waits for the lifespan-started signal.** GitHub Actions tails the new task's CloudWatch log group, looking for the `lifespan_started` event with the SHA matching the deploy's image. A bounded timeout (default 5 minutes) is applied.
- **A timeout is a deploy failure.** If the new task does not emit `lifespan_started` within the timeout, the deploy job fails. ECS's deployment circuit breaker (configured on the service) detects the failed deployment and reverts to the previous task definition revision, restoring the prior known-good state automatically.
- **Health-check failure during rollout is also a deploy failure.** If new tasks start but fail readiness probes, ECS's health-check rollout halts and the circuit breaker rolls back. The pipeline observes this as a failed deploy.
- **The deploy does not declare success on the absence of error.** A pipeline that exits 0 because the deploy command returned 0 — but no new task emitted `lifespan_started` — is exactly the failure mode this record forbids. The pipeline asserts the positive signal.

### Rollback

Rollback is the same mechanism as deploy: a new task-definition revision pointing at the previous SHA's image. Specifically:

- **ECS deployment circuit breaker** (configured: `enable = true, rollback = true`) automatically rolls back when a new deployment fails its health-check rollout. This is the primary rollback path; it requires no human action and completes inside the deployment window.
- **Manual rollback** is a re-run of the deploy pipeline targeting a previous SHA. It is the same code path as a forward deploy; the only change is which SHA is referenced.
- **Forward-fix is preferred over manual rollback** for issues that surface after a deploy has stabilized. The combination of "circuit breaker handles the boot-time failures" and "fast pipeline for forward fixes" makes manual rollback rare.

### Authentication

GitHub Actions authenticates to AWS via OpenID Connect federation:

- **No long-lived AWS credentials in GitHub secrets.** The repository's GitHub Actions OIDC provider is configured as a trusted identity provider in AWS IAM; the role assumed by the workflow is constrained to ECR-push and ECS-update-service permissions for the application.
- **The role's trust policy restricts which workflows and branches may assume it.** The OIDC subject claim is checked against `repo:<org>/<repo>:ref:refs/heads/main` (and the corresponding tag refs for release deploys); workflows from other branches cannot assume the role.
- **Per-environment role separation.** Production deploys assume a role distinct from staging deploys; the production role's trust policy is stricter (e.g., restricted to specific workflow files, not just any workflow on `main`).

### What this record does not change

- The application's source layout, dependency manifest, and Python version are unchanged.
- The application's lifespan, port binding, configuration model, and observability shape are unchanged.
- Local development workflows are unchanged ([environment-parity.md](environment-parity.md)).
- Per-feature CI tests, linters, type checks, and code-quality gates are unchanged.

## Consequences

**Positive:**

- Promotion across environments is configuration-only. The image that was tested in CI is the image that runs in production.
- Rollback is automatic for deploy-time failures. The circuit breaker requires no human action; the previous good state is preserved.
- Deploy validation is tied to the lifespan-completion signal, not to a fuzzy orchestrator state. A "successful" deploy is a deploy whose new task has actually booted.
- The pipeline holds no long-lived AWS credentials. A GitHub repository compromise does not produce permanent AWS access.
- Image identity is permanent. Every SHA tag identifies a specific source state, lockable into audit logs, runbooks, and incident reports.

**Tradeoffs accepted:**

- One image per commit means the registry accumulates images at the rate of merges to `main`. Acceptable: ECR has lifecycle policies that retain a bounded set of recent SHAs and prune older ones; rare access to old SHAs is a deliberate audit/forensics path, not a hot path.
- Builds run on every commit to `main` regardless of which files changed. Acceptable: the build is small, the cache is effective, and the alternative — selective builds — leaks build-conditional logic into source control.
- Deploy validation polls logs rather than receiving an active signal from the application. Acceptable: log-tailing is the canonical operations interface; introducing an additional control-plane endpoint would couple the pipeline to a custom application surface.
- Per-environment role separation is more configuration than a single role would be. Acceptable: a production credential blast radius distinct from staging is the only way to make accidental staging-prod cross-deploys impossible.

**Risks and mitigations:**

- **The lifespan-started log event is renamed without updating the deploy validation.** Validation times out on every deploy, blocking promotion. *Mitigation:* the event name is part of the operational contract; renames go through review; the deploy pipeline's expected event name is read from a single shared constant.
- **A long-running phase 5 handshake legitimately takes more than 5 minutes.** Validation times out though the deploy is fine. *Mitigation:* the timeout is configurable per service; long-running boot work is reviewed and either bounded or moved to background.
- **Two near-simultaneous deploys race in ECS.** A second deploy lands while the first is mid-rollout; circuit breaker behaviour interacts. *Mitigation:* the pipeline serializes deploys per environment; concurrent runs are queued.
- **The OIDC trust policy is misconfigured to allow assumption from any branch.** A pull-request workflow can assume the deploy role. *Mitigation:* the trust policy's `sub` claim is reviewed; integration tests assert that an assume from a non-`main` ref is rejected.
- **A SHA's image is purged from ECR before a rollback to it is attempted.** Rollback is impossible. *Mitigation:* the lifecycle policy retains enough recent SHAs to cover plausible rollback windows; production deploys protect their immediate predecessor against pruning.

## Confirmation

Compliance is verified by:

- **Code review.** No `latest` tag references in deploy code. No environment-specific build-args. No long-lived AWS credentials in repository secrets. Task definitions reference SHA-tagged images explicitly.
- **Pipeline tests.** A canary deploy (against a non-production environment) verifies the full pipeline: build, push, release, deploy, validation. A deliberately-failing deploy (e.g., against an image whose entrypoint exits) verifies that the circuit breaker rolls back.
- **OIDC tests.** A workflow attempting to assume the deploy role from a non-allowed branch is rejected by the trust policy. The role's permissions allow only the documented ECR/ECS actions.
- **Operational checks.** Deploy duration, validation timeouts, circuit-breaker rollbacks, and image-purge events are visible on a dashboard.

## Source References

1. The Twelve-Factor App — Build, Release, Run (Factor V)
   - URL: <https://12factor.net/build-release-run>
   - Accessed: 2026-04-29
   - Relevance: Establishes the strict separation of stages: "build = code → executable bundle"; "release = build + config"; "run = the orchestrator executes the release." Grounds the rule that the same build is promoted across environments and that configuration is injected at release.

2. AWS — Amazon ECS Deployment Circuit Breaker
   - URL: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the deployment circuit breaker (`enable = true, rollback = true`), which monitors task health and rolls back to the prior task definition on failed rollout. Grounds the auto-rollback contract.

3. AWS — Amazon ECR Lifecycle Policies
   - URL: <https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_examples.html>
   - Accessed: 2026-05-08
   - Relevance: Documents lifecycle policies for retaining a bounded set of recent images and pruning older ones. Grounds the registry-growth tradeoff and the rollback-window guarantee.

4. GitHub Actions — Configuring OpenID Connect in AWS
   - URL: <https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services>
   - Accessed: 2026-05-08
   - Relevance: Documents the OIDC federation setup for AWS access without long-lived credentials, including the `sub` claim shape used by trust policies. Grounds the credential model for the pipeline.

5. AWS — IAM Roles for Service Accounts (Trust Policy `sub` Claim)
   - URL: <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the trust-policy condition keys (including `token.actions.githubusercontent.com:sub`) used to restrict which GitHub workflows may assume an AWS role. Grounds the per-environment role separation rule.

6. Docker — Multi-stage Builds
   - URL: <https://docs.docker.com/build/building/multi-stage/>
   - Accessed: 2026-05-08
   - Relevance: Documents the multi-stage build pattern that separates build tools from runtime artifacts. Grounds the rule that the deployed image carries only runtime layers, not build dependencies.

7. The Twelve-Factor App — Disposability (Factor IX)
   - URL: <https://12factor.net/disposability>
   - Accessed: 2026-04-29
   - Relevance: Establishes that processes must be disposable (fast startup, graceful shutdown, robust against sudden death). Grounds the deploy-validation contract: a release is "successful" when a new disposable process boots, runs, and exits the lifespan startup phase cleanly.

## Change Log

- 2026-05-08: Created. Establishes the build-release-run pipeline: one image per commit identified by Git SHA (no `latest`, no environment-specific build-args); release = image + per-environment task definition (configuration injected at release time, not at runtime); run = ECS Fargate task whose successful boot is observed via the `lifespan_started` log signal; auto-rollback via ECS deployment circuit breaker; OIDC federation for GitHub Actions to AWS authentication; per-environment role separation. Defers infrastructure provisioning (Terraform, IAM, ECR repository creation, ALB listener rules) to operations infrastructure code.
