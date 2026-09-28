---
status: Accepted
date: 2026-07-06
applies: target
scope: Application startup phases, readiness, and shutdown.
---

# Application Lifecycle

## Context

Composition order matters: configuration before services, services before plugins, extension points filled before the capabilities that own them initialize, everything before traffic. The app runs as two or more replicas ([plugin-architecture.md](plugin-architecture.md)).

Current code (`app/server/lifespan.py`):
- Loads settings slices and logs their keys, and builds the JWKS clients without fetching keys (a missing `ISSUER_CONFIG` logs a warning and continues).
- Makes network calls before traffic in two places: the directory warmup, when `DIRECTORY_REQUIRE_STARTUP_WARMUP` opts in, and `access/sync`'s `startup_warmup`, whose adapter assumes an AWS role through STS while `get_aws_client` builds it. The second one makes STS a hard boot dependency of the whole app on behalf of one business feature.
- Discovers plugins by walking `packages/` and `modules/` (`auto_discover_plugins`), which logs and skips a package that fails to import.
- Collects i18n resources through `register_i18n_resources`, then initializes the translator strictly; failure aborts boot.
- Calls `register_slack_commands`, `register_routes` and `startup_warmup`; features construct their services lazily or inside `startup_warmup`. `access/request` and `access/sync` subscribe to in-process events there.
- Registers legacy `modules/` handlers by hand, starts scheduled tasks only when `ENVIRONMENT == "production"` (Tier-2 jobs take a lease from the idempotency store), then starts Socket Mode.
- On shutdown, stops scheduled tasks, then the Slack provider.

Phases are logged with a `phase` field, but there is no single ordered sequence, no eager service validation, and plugin load errors are not fatal.

## Decision

One ASGI lifespan with ordered phases, each logged with its name:

1. **Configuration.** Load the base configuration file and the one for `ENVIRONMENT`, plus secrets, and validate every settings slice ([configuration.md](configuration.md)). Invalid or missing configuration fails boot here.
2. **Core services.** Register a factory per `contracts` Protocol in the svcs registry, then resolve each once from a startup container ([dependency-injection.md](dependency-injection.md)). Construction and static validation only, never a network call.
3. **Plugin loading.** Read the entry points declared in `pyproject.toml` ([plugins.md](plugins.md)). Skip, before registration, every plugin that the environment's configuration file disables. Register the rest, then run the credential checks the enabled plugins declare (below). What a plugin's boot failure does depends on its layer and the kind of failure ([plugins.md](plugins.md)).
4. **Extension points.** For each capability, in its declared order, call its hookspecs once to collect strategy objects (an `ApprovalPolicy`, an alert-action handler), then initialize the capability with them. A capability never initializes with an extension point still unfilled.
5. **Feature registration.** Registration hookspecs fire: routes mount, platform handlers attach, jobs register with the scheduler. Registries freeze at `yield`.
6. **Transport.** HTTP serves; Socket Mode connects; the scheduler starts.
7. **Shutdown.** Reverse order, each step with a bounded budget, completing inside the platform's grace window (30 s on ECS; `terminationGracePeriodSeconds` on Kubernetes and OpenShift).

**Only deploy-coupled defects abort boot.** A defect that ships with the image or the checked-in configuration (an import error, a hookimpl that raises, an invalid host or capability setting) aborts boot: during a rolling deploy the old tasks keep serving, and the circuit breaker's rollback fixes it. A fault in state that changes without a deploy (an IAM role or permission removed, a secret rotated, a vendor down) never aborts boot. It would turn a one-feature fault into a whole-app outage at the next task restart or scale-out, and a rollback cannot fix it.

**Credential checks: opt-in per plugin, report, never abort.** The only network calls before `yield` are credential checks. Any feature or capability whose work depends on a credential may opt in by declaring one through the `register_credential_checks` hookspec ([plugins.md](plugins.md)), and a registered service may declare one the same way. Declaring one is the plugin author's choice; a plugin that declares none makes no network call at boot. A check is a single cheap, read-only call on the API the plugin uses, one attempt, with a bounded timeout, run through its adapter so the result is a classified `OperationResult`. It tests authentication, authorization and reachability, not data (an empty result is a pass). Its purpose is to alert within seconds of a deploy or restart that a credential is broken, even for a feature nobody is using, without taking the app down. `access/sync` (the AWS Identity Store role) and the directory capability (the Google service account) are the first users.
- `UNAUTHORIZED`, `PERMANENT_ERROR` or `NOT_FOUND` (role that can't be assumed, missing permission, wrong resource id) logs ERROR `credential_check_failed`. The feature stays registered: its calls return that status until the credential is fixed, and because credentials refresh themselves it recovers without a restart.
- `TRANSIENT_ERROR` (timeout, throttling, 5xx, connection error) logs WARNING `credential_check_inconclusive`.

The error and warning alarms ([observability.md](observability.md)) are the alert path. Boot checks run only at task start, so a credential that breaks mid-life surfaces at first use.

Nothing else calls out before traffic: no connectivity probes, no warmups. Client construction never calls the network ([outbound-clients.md](outbound-clients.md)). Local resources the process owns, such as a database file baked into the image, may be opened.

**Fail fast on deploy-coupled defects.** Any other exception before `yield` aborts boot. The ECS deployment circuit breaker counts tasks that never reach RUNNING and rolls the deployment back ([ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)). The degraded starts are: JWKS issuer gaps ([security.md](security.md)), a feature whose settings slice fails validation, which is skipped with a CRITICAL `plugin_boot_failed` event ([plugins.md](plugins.md)), and the credential-check results above.

**Every replica runs the same lifespan.** No phase assumes it is the only process: nothing keeps shared state in memory, and a scheduled job runs once across replicas by taking a lease from the coordination contract before each run ([reliability.md](reliability.md)).

**Readiness** means all phases completed. The ASGI server accepts connections only after lifespan startup returns, so any response from the static probe endpoint already means ready. Probe endpoints and their policy are defined in [health-checks.md](health-checks.md). Deploy validation watches readiness, not logs ([cloud-portability.md](cloud-portability.md)).

**Crash-only discipline.** The process must tolerate being killed at any phase; recovery is restart, not repair. [reliability.md](reliability.md) makes the side effects safe.

## Consequences

- "Why isn't my service available?" is answerable from phase logs; a hang is attributable to a phase.
- Eager validation trades slower boot for no construction failures mid-request.
- Strategy collection before capability initialization makes a missing policy a boot failure, not a runtime error.
- Cost: every service and plugin must be constructible at boot in every environment, including CI.

## Checks

- Lifespan test: phases log in order; a poisoned factory, an unimportable plugin or a raising hookimpl aborts before `yield`; a feature with an invalid settings slice is skipped, logs `plugin_boot_failed`, and the app serves.
- Boot test: under a `socket.connect` spy, startup opens outbound connections only from declared credential checks.
- Boot test: a credential check returning `UNAUTHORIZED` logs `credential_check_failed` at ERROR and one returning `TRANSIENT_ERROR` logs `credential_check_inconclusive` at WARNING; in both cases boot completes and the feature stays registered.
- Boot test: a plugin disabled in configuration is never registered; every extension point is filled before its capability initializes.
- Readiness flips only after `yield`; shutdown completes within budget under test.
- Review: no scheduled job runs without a lease.

## Migration

Tickets: TASK-58 (coordination contract and leases), TASK-109 (service registry), TASK-110 (plugin loading), TASK-98 (lazy AssumeRole), TASK-126 (credential checks and feature isolation), TASK-128 (directory check).

Tolerated until closed:
- plugin discovery by filesystem walk, with import errors logged and skipped;
- services built lazily or in `startup_warmup` hookimpls instead of an eager registry phase;
- network I/O before `yield` that aborts boot on failure: the opt-in directory warmup, and `access/sync`'s AssumeRole during client construction;
- a feature whose settings fail validation aborts boot instead of being skipped;
- in-process event subscriptions registered in `startup_warmup` by `access/request` and `access/sync`;
- scheduled tasks gated on `ENVIRONMENT == "production"` and started from `jobs/scheduled_tasks.py`, with leases from the idempotency store;
- legacy `modules/` handlers registered by hand after feature registration.

**Changes:**
- 2026-09-24: phases aligned with plugin-architecture (config-file enablement, registry validation, extension-point collection, multi-replica); `applies` corrected to `target`.
- 2026-09-25: only deploy-coupled defects abort boot; a feature with invalid settings is skipped; boot credential checks alert but never abort; readiness is lifespan completion.
