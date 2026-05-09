---
title: "Environment Parity"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application, operations]
concerns: [configuration]
constrained_by: [cloud-portability.md, configuration-ownership.md, package-management.md, logging-observability.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Environment Parity

## Context and Problem Statement

The application runs in several distinct contexts: a developer's laptop during local work, a continuous-integration runner during automated tests, a non-production cloud deployment for shared verification, and a production cloud deployment serving users. Treating these as fundamentally different things — different code paths, different SDK versions, different runtime configurations — produces the well-known dev/prod gap: bugs that "only happen in production," and changes that pass tests but break on deploy.

The problem this record addresses: **what is the standard for keeping the application's behaviour consistent across all the contexts in which it runs — code, dependencies, runtime, configuration shape, observability — so that promotion between environments is a configuration change, not a behavioural roll of the dice?** The answer determines:

1. Whether local development uses the same Python version, the same dependency lock, and the same artifact shape as production.
2. Whether external backing services (DynamoDB, SQS, Slack, etc.) are stubbed locally with the same Protocol contracts as production, or whether local code paths diverge from production code paths.
3. Whether environment-specific behaviour is encoded by branching in code (`if ENV == "prod"`) or strictly by configuration values consumed by environment-agnostic code.
4. Whether logs, metrics, traces, and lifecycle events have the same shape and routing in every environment, so that operational tooling works the same everywhere.

**Constraints:**

- The application is a stateless process whose configuration is read from environment variables and validated at startup ([cloud-portability.md](cloud-portability.md), [configuration-ownership.md](configuration-ownership.md)). Any environment-dependent behaviour is therefore expressible as configuration.
- Logs are written to stdout/stderr; the surrounding execution environment captures and routes them ([cloud-portability.md](cloud-portability.md), [logging-observability.md](logging-observability.md)). The application does not implement environment-specific log routing.
- Dependencies are locked through a single tool ([package-management.md](package-management.md)). The same lock file is used in development, CI, and production builds; transitive dependency drift between environments is not permitted.
- Boot is deterministic and ordered ([application-lifecycle.md](application-lifecycle.md)). Phase 6 (background) is suppressed by configuration in non-production runs; phases 1–5 run identically everywhere.
- Backing services with no local equivalent (Slack, identity providers) are accessed through the same Protocol surface in development as in production; the implementation behind the Protocol may be a fake.

**Non-goals:**

- This record does not pick the build, release, or deploy mechanism — those are owned by [build-release-run-pipeline.md](build-release-run-pipeline.md).
- This record does not pick the local development tool (Docker Compose, devcontainer, native virtual environment). Multiple paths are permitted as long as each produces the same behaviour as the deployed image.
- This record does not own per-environment secret rotation or secret store selection — that is owned by [configuration-ownership.md](configuration-ownership.md) and the deployment platform.
- This record does not redefine which settings are environment-dependent. That catalogue belongs to each settings class per [configuration-ownership.md](configuration-ownership.md).

## Considered Options

**Option 1 — Strict parity by construction: same source tree, same Python version, same dependency lock everywhere; only configuration differs; backing services stubbed in local with Protocol-conformant fakes; no branches on environment in business code.** Local development runs Python directly against the same lock file (typically inside a devcontainer or GitHub Codespaces) with hot reload. Backing services use a settings-driven backend toggle (`memory://` vs `<vendor>://`, in-memory queue vs the cloud queue). Lifespan phase 6 (background) is suppressed in non-production by the canonical environment indicator.

**Option 2 — Loose parity: each environment runs whatever is convenient.** Local uses one Python version; CI uses another; the deployed image uses a third. Backing services are mocked by hand in tests, stubbed inline in development, real in production.

**Option 3 — Local-as-production: every developer must run a real cloud sandbox.** No local backing-service stubs; no environment-aware code paths.

## Decision Outcome

**Chosen: Option 1 — strict parity by construction; configuration is the only environment-dependent input; backing services have Protocol-conformant local fakes.**

This is the only option that lets a developer reason about a change locally and have that reasoning hold in production. Loose parity (Option 2) reproduces the dev/prod gap as a feature. Local-as-production (Option 3) makes day-to-day work depend on an external cloud, which is bad for iteration speed and bad for offline work; in particular, it's a very high cost to pay for the parity benefit, when Protocol-backed local fakes give the same semantic guarantee with none of the cost.

**Parity is on source, dependencies, runtime semantics, and configuration shape — not on the runtime packaging.** The deployed image is a packaging detail produced by the build pipeline ([build-release-run-pipeline.md](build-release-run-pipeline.md)); local development runs the same source against the same lock file under the same Python interpreter without rebuilding the production image on every change. Hot reload, not container rebuild, is the local iteration mechanism.

### What is the same in every environment

- **Python version.** The same minor Python version (e.g., 3.13) runs in local development, CI, and the deployed image. Project metadata declares the version once ([project-metadata.md](project-metadata.md), [package-management.md](package-management.md)); the local tooling and the Dockerfile both consume that declaration.
- **Dependency closure.** The same `uv` (or equivalent) lock file is used in local development, CI, and the deployed image. Production never installs a dependency that local does not have, and vice versa.
- **Code path.** The same source tree runs in every environment. There are no `if ENV == "prod"` branches in business code; environment-dependent behaviour is mediated through configuration values consumed by environment-agnostic code.
- **Lifespan ordering.** The same six startup phases run, in the same order, in every environment. Phase 6 (background) is suppressed by configuration in non-production runs (see "The canonical environment indicator" below); registration in phase 3 still runs.
- **Process count.** A single application process serves traffic in local development. Production runs N parallel processes for capacity; local runs one for predictability. The application's contract is invariant either way (statelessness ensures one-or-N produce the same end state), but the local-development *experience* is one process — there is no orchestrator and no queue contention to reason about.
- **Logging shape.** The same `structlog` pipeline produces the same JSONL records on stdout in every environment. Levels and verbosity are configurable, but the schema is invariant.
- **Observability routing.** Logs go to stdout; the execution environment captures them. There is no environment-specific log shipper inside the application.
- **Configuration shape.** Settings classes have the same fields in every environment. A field's value differs; its presence and type do not.

### What is different — and how

The list of things that differ between environments is short, named, and exhausted by configuration:

- **Backing-service backends.** A `*_BACKEND` setting (e.g., `QUEUE_BACKEND=memory|<vendor>`, `STORAGE_BACKEND=memory|<vendor>`) selects between a Protocol-conformant in-memory implementation and the cloud-vendor implementation. The application's domain code depends on the Protocol; the backend choice is invisible to it.
- **External integrations with no local equivalent.** Slack, identity providers, third-party APIs. Three postures are permitted:
  - A local *fake* that implements the integration's Protocol with deterministic responses (e.g., a stub identity provider that returns a fixed JWT for any request). Used for local development and most tests.
  - A real *sandbox tenant* (an IdP test tenant) used for end-to-end tests where the fake's coverage is insufficient.
  - **A shared real tenant where the development app cohabits with the production app via configured prefixes.** The application's Slack integration uses this posture: a single Slack workspace hosts both the production app and a development app, distinguished at the Slack-side by configured command prefixes (e.g., `/sre …` vs `/dev-sre …`) and at the application-side by the same configuration value. The Slack workspace becomes a real backing service for development without needing a separate workspace; routing of an inbound interaction to the dev or prod app is determined entirely by which command was invoked. This is configuration-driven separation, fully consistent with the no-environment-branches rule.
- **Secrets.** Local development uses a `.env` file (gitignored) for credentials and tokens. CI uses repository secrets. Production reads from the deployment platform's secret-injection mechanism. In all cases the application reads the same environment-variable names; the source differs.
- **Resource sizing.** Connection pool sizes, timeout defaults, log levels may differ between local and production for ergonomic reasons (e.g., shorter timeouts in local to fail fast). These are settings; their *names* and *types* are the same.

### The canonical environment indicator

The application has one canonical environment indicator, exposed through the security/lifecycle settings class. Possible values: `local`, `ci`, `dev`, `staging`, `prod`. Code that needs to know "is this production?" reads `settings.environment == "prod"` (or its equivalent typed predicate); ad-hoc reads of `os.environ` for environment detection are prohibited.

The indicator drives a small number of well-defined effects:

- **Phase 6 (background) gating.** Non-`prod` values suppress the runner ([background-execution.md](background-execution.md)); registration in phase 3 still runs.
- **Strictness of dev-bypass paths.** Any "dev convenience" path (a JWT bypass token, a fake-identity injection) is gated to non-`prod` values *and* additionally guarded at the dependency level ([api-security.md](api-security.md)); they cannot be enabled in `prod` even by misconfiguration.
- **Log level defaults.** A non-`prod` environment may default to `debug`; `prod` defaults to `info`.

The indicator does *not* drive:

- Choice of backing-service backend (which uses its own `*_BACKEND` setting).
- Choice of external integration target (which uses the integration's own URL setting).
- Branches in business logic.

### Local development workflow

The canonical local-development path is **hot reload on Python directly, inside a devcontainer or GitHub Codespaces**:

- The devcontainer (or Codespaces image) is the *development environment* — it carries the Python toolchain, `uv` (or equivalent), the system packages the application needs at runtime, and editor tooling. It is not the same artifact as the deployed image; it is the developer's workbench.
- Inside the devcontainer, the application runs as `uvicorn app.main:app --reload`. A code change saves; uvicorn restarts the application; the change is observable in seconds.
- The application runs as a single process. Lifespan phase 6 (background) is suppressed via the canonical environment indicator. Backing-service settings select in-memory or sandbox-tenant backends; no production cloud dependency.
- The deployed container image is a *parity-verification artifact*, used occasionally — to confirm a behaviour reproduces with the production runtime, to check image-build hermeticity. It is not part of the inner-loop iteration cycle.

A native (non-devcontainer) virtual environment is permitted for developers whose local toolchain matches the devcontainer's; the parity guarantee is identical because the same lock file and Python version are used. Devcontainer or Codespaces is preferred because it removes "what's on my host" from the parity equation.

What unifies all variants: they all run *the same source tree* with *the same lock file* under *the same Python interpreter version* and *the same configuration shape* — produced by Protocol-conformant local fakes for backing services, and real sandbox tenants for the few external integrations that do not have local equivalents.

### CI parity

Continuous integration runs the same test suite the developer runs locally. CI does not introduce its own dependency overrides, its own settings, or its own Python version. CI's environment indicator is `ci`; it suppresses phase 6 (per the standard), but otherwise behaves like local development with `*_BACKEND=memory` for every backing service.

### What this record does not change

- Per-feature settings catalogues remain owned by their feature.
- Per-vendor credential placement and secret-store selection remain owned by [configuration-ownership.md](configuration-ownership.md).
- The lifespan, logging, and plugin standards are unchanged.

## Consequences

**Positive:**

- "It works on my machine" becomes a meaningful statement: if it works locally with the standard backend toggles, the only remaining variables in production are the backing-service URLs and credentials.
- Bugs that surface in production reproduce locally with high reliability, because the code paths and dependencies are the same.
- A new developer onboarding runs the application in five minutes against in-memory backends; they don't need cloud credentials to make and verify code changes.
- CI is a faithful preview of a deployed run, not a separate "test environment" with its own quirks.

**Tradeoffs accepted:**

- Maintaining Protocol-conformant local fakes is ongoing work. Acceptable: the cost is paid once per backing service and amortizes over every developer hour.
- Some failures will only surface against the real backing service (a DynamoDB consistency edge case, a Slack API behaviour). Acceptable: end-to-end tests against the real sandbox cover the residual; local fakes are not advertised as full simulators.
- The discipline against `if ENV == "prod"` branches is a real constraint. Acceptable: every such branch is an opportunity for one environment to diverge silently from another.

**Risks and mitigations:**

- **A developer adds a backing-service call without a local fake.** Local development against that feature breaks. *Mitigation:* code review checks that any new backing-service Protocol has an in-memory implementation; a CI test asserts the in-memory backend produces a complete result.
- **A settings field is added that exists only in production.** Non-production runs fail to start, or vice versa. *Mitigation:* settings classes declare every field; a missing required field fails fast at lifespan phase 1; tests validate the shape under all backend configurations.
- **The local image drifts from the deployed image.** Acceptance tests pass locally but fail on deploy. *Mitigation:* the deploy validation step ([build-release-run-pipeline.md](build-release-run-pipeline.md)) runs lifespan-success checks against the deployed image; CI builds the same image developers run locally.

## Confirmation

Compliance is verified by:

- **Code review.** No `if ENV == "prod"` branches in business code. Settings classes carry every environment-relevant field; readers do not call `os.environ.get(...)` outside settings construction.
- **Static analysis.** A check forbids `os.environ` reads outside `app/infrastructure/<service>/settings.py` files and `app/main.py`'s composition root.
- **Tests.** A boot test runs the lifespan with `*_BACKEND=memory` for all backing services and asserts phases 1–5 complete successfully. A second boot test runs with the production-style backend toggles against test sandboxes and asserts the same.
- **Local development.** A `make dev` (or equivalent) command starts the application locally with sensible defaults and reaches a healthy `/health/readiness` response in well under a minute.

## Source References

1. The Twelve-Factor App — Dev/Prod Parity (Factor X)
   - URL: <https://12factor.net/dev-prod-parity>
   - Accessed: 2026-04-29
   - Relevance: Establishes the principle that "development, staging, and production [should be] as similar as possible" — small time gap (continuous deployment), small personnel gap (developers deploy), small tools gap (same backing services). Grounds every rule in this record.

2. The Twelve-Factor App — Backing Services (Factor IV)
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-04-29
   - Relevance: Establishes that backing services are attached resources accessed via configuration. Grounds the rule that backing-service backends are settings-toggled; the application code does not branch on which backend it uses.

3. The Twelve-Factor App — Config (Factor III)
   - URL: <https://12factor.net/config>
   - Accessed: 2026-04-29
   - Relevance: Establishes that configuration is "everything that is likely to vary between deploys" and lives in environment variables. Grounds the rule that environment-dependent behaviour is mediated by configuration values, not code branches.

4. The Twelve-Factor App — Build, Release, Run (Factor V)
   - URL: <https://12factor.net/build-release-run>
   - Accessed: 2026-04-29
   - Relevance: Establishes the strict separation of build, release, and run stages; release is the build joined to per-environment configuration. Grounds the rule that the same image (build artifact) is promoted across environments with only configuration differing.

5. The Twelve-Factor App — Logs (Factor XI)
   - URL: <https://12factor.net/logs>
   - Accessed: 2026-04-29
   - Relevance: Establishes that an application "should not attempt to write to or manage logfiles. Instead, each running process writes its event stream, unbuffered, to stdout." Grounds the rule that observability routing is the execution environment's job, not the application's, and is identical in every environment.

## Change Log

- 2026-05-08: Created. Establishes strict environment parity on source, dependencies, runtime semantics, and configuration shape — *not* on runtime packaging. Names hot reload inside a devcontainer or Codespaces (uvicorn `--reload` against host Python with the same lock file) as the canonical local-development workflow; the deployed container image is occasional parity-verification, not inner-loop tooling. Single-process posture in local with phase 6 (scheduled jobs) suppressed. Backing-service Protocol fakes are the local mechanism for cloud services; real sandbox tenants are permitted for integrations that do not have local equivalents, and a third posture — cohabitation in a shared real tenant via configured prefixes (e.g., the application's `/sre` vs `/sredev` Slack-command separation) — is named explicitly as configuration-driven separation. Specifies the canonical environment indicator and the small set of effects it drives (phase 6 gating, dev-bypass strictness, log-level defaults). Forbids `if ENV == "prod"` branches in business code; environment-dependent behaviour is mediated by configuration values consumed by environment-agnostic code.
