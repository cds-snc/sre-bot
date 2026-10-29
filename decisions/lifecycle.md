---
status: Accepted
date: 2026-10-15
applies: target
scope: Application startup phases, readiness, and shutdown.
---

# Application Lifecycle

## Context

Composition order matters: configuration before services, services before plugins, extension points filled before the capabilities that own them initialize, everything before traffic. The app runs as two or more replicas ([plugin-architecture.md](plugin-architecture.md)).

Current code (`app/server/lifespan.py`):
- Loads settings slices and logs their keys, and builds the JWKS clients without fetching keys (a missing `ISSUER_CONFIG` logs a warning and continues).
- Makes network calls before traffic in two places: the directory warmup, when `[directory] require_startup_warmup` opts in, and `access/sync`'s `startup_warmup`, whose adapter assumes an AWS role through STS while `get_aws_client` builds it. The second one makes STS a hard boot dependency of the whole app on behalf of one business feature.
- Loads plugins from the `pyproject.toml` entry points (`load_plugins`); a plugin that fails to import aborts boot.
- Collects i18n resources through `register_i18n_resources`, then initializes the translator strictly; failure aborts boot.
- Calls `register_slack_commands`, `register_routes` and `startup_warmup`; features construct their services lazily or inside `startup_warmup`. `access/request` and `access/sync` subscribe to in-process events there.
- Registers legacy `modules/` handlers by hand and starts Socket Mode, then starts scheduled tasks when `[scheduler] enabled` (true in production only), whether or not the Slack app initialised (Tier-2 jobs take a lease from the coordination contract).
- On shutdown, stops scheduled tasks, then the Slack provider.

Phases are logged with a `phase` field, but there is no single ordered sequence, no eager service validation, and plugin load errors are not fatal.

## Decision

One ASGI lifespan with ordered phases, each logged with its name:

1. **Configuration.** Load the base configuration file and the one for `ENVIRONMENT`, plus secrets, and validate every settings slice ([configuration.md](configuration.md)), vendor slices with the host slices: a present tenant entry with a missing secret or a bad shape fails boot here, and so does a transport switched on without its vendor's tenant entry, with no network call: the host's case of the rule that an enabled component whose required vendor is not configured aborts boot ([plugins.md](plugins.md)). An absent entry with its transport off is a vendor left unconfigured, never a failure. Invalid or missing configuration fails boot here. Logging is configured first, from the identity and `[logging]` slices, so every later configuration event, a failure included, is part of the one JSON stream ([observability.md](observability.md)). This phase runs in the app factory, `create_app()`, started with `uvicorn --factory`, before the ASGI app is built: Starlette fixes the middleware stack on the app's first ASGI call, and the lifespan startup is that call, so a value a middleware needs (the request body limit, the CORS list) must be known first ([uvicorn settings](https://uvicorn.dev/settings/), [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)). ASP.NET Core builds its configuration in the same place, before the pipeline ([ASP.NET Core environments](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/environments)). The factory builds the middleware from the validated slices and hands the loaded configuration to the lifespan, which runs the remaining phases and never reloads it. An invalid configuration still exits the process before it serves, so the circuit breaker rolls the deploy back. The phase ends by logging the generated `configuration_summary` ([configuration.md](configuration.md)), never a hand-kept list of keys.
2. **Core services.** Register a factory per `contracts` Protocol in the svcs registry, then resolve each once from a startup container ([dependency-injection.md](dependency-injection.md)). Construction and static validation only, never a network call.
3. **Plugin loading.** Read the entry points declared in `pyproject.toml` ([plugins.md](plugins.md)). Skip, before registration, every plugin that the environment's configuration file disables. Register the rest, validating each enabled plugin's slices, then log one `plugin_configuration_summary` and run the credential checks the enabled plugins declare (below). What a plugin's boot failure does depends on its layer and the kind of failure ([plugins.md](plugins.md)).
4. **Extension points.** For each capability, in its declared order, call its hookspecs once to collect strategy objects (an `ApprovalPolicy`, an alert-action handler), then initialize the capability with them. A capability never initializes with an extension point still unfilled.
5. **Feature registration.** Registration hookspecs fire: routes mount, platform handlers attach, jobs register with the scheduler. Registries freeze at `yield`.
6. **Transport.** HTTP serves; Socket Mode connects; the scheduler starts.
7. **Shutdown.** Reverse order, each step with a bounded budget, completing inside the platform's grace window (30 s on ECS; `terminationGracePeriodSeconds` on Kubernetes and OpenShift).

**Only deploy-coupled defects abort boot.** A defect that ships with the image or the checked-in configuration (an import error, a hookimpl that raises, an invalid setting in any layer, a required vendor not configured) aborts boot: during a rolling deploy the old tasks keep serving, and the circuit breaker's rollback fixes it ([deployment.md](deployment.md)). A fault in state that changes without a deploy (an IAM role or permission removed, a secret rotated, a vendor down) never aborts boot. It would turn a one-feature fault into a whole-app outage at the next task restart or scale-out, and a rollback cannot fix it.

**Credential checks: opt-in per plugin, report, never abort.** The only network calls before `yield` are credential checks. Any feature or capability whose work depends on a credential may opt in by declaring one through the `register_credential_checks` hookspec ([plugins.md](plugins.md)), and a registered service may declare one the same way. Declaring one is the plugin author's choice; a plugin that declares none makes no network call at boot. A check is a single cheap, read-only call on the API the plugin uses, one attempt, with a bounded timeout, run through its adapter so the result is a classified `OperationResult`. It tests authentication, authorization and reachability, not data (an empty result is a pass). Its purpose is to alert within seconds of a deploy or restart that a credential is broken, even for a feature nobody is using, without taking the app down. `access/sync` (the AWS Identity Store role) and the directory capability (the Google service account) are the first users.
- `UNAUTHORIZED`, `PERMANENT_ERROR` or `NOT_FOUND` (role that can't be assumed, missing permission, wrong resource id) logs ERROR `credential_check_failed`. The feature stays registered: its calls return that status until the credential is fixed, and because credentials refresh themselves it recovers without a restart.
- `TRANSIENT_ERROR` (timeout, throttling, 5xx, connection error) logs WARNING `credential_check_inconclusive`.

The error and warning alarms ([observability.md](observability.md)) are the alert path. Boot checks run only at task start, so a credential that breaks mid-life surfaces at first use.

Nothing else calls out before traffic: no connectivity probes, no warmups. Client construction never calls the network ([outbound-clients.md](outbound-clients.md)). Local resources the process owns, such as a database file baked into the image, may be opened.

**Fail fast on deploy-coupled defects.** Any other exception before `yield` aborts boot. The ECS deployment circuit breaker counts tasks that fail to reach RUNNING, and tasks replaced because a load balancer or container health check failed; at two replicas it trips after three consecutive failures and rolls back to the last COMPLETED deployment ([ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html), [deployment.md](deployment.md)). The degraded starts are JWKS issuer gaps ([security.md](security.md)) and the credential-check results above. An enabled plugin whose settings slice fails validation, or whose required vendor or capability is not configured, is a configuration defect that ships with the deploy: it aborts boot with a CRITICAL `plugin_boot_failed` event naming the key ([plugins.md](plugins.md)).

**Every replica runs the same lifespan.** No phase assumes it is the only process: nothing keeps shared state in memory, and a scheduled job runs once across replicas by taking a lease from the coordination contract before each run ([reliability.md](reliability.md)).

**Readiness** means all phases completed. The ASGI server accepts connections only after lifespan startup returns, so any response from the static probe endpoint already means ready. Probe endpoints and their policy are defined in [health-checks.md](health-checks.md). Deploy validation watches readiness, not logs ([cloud-portability.md](cloud-portability.md)).

**Crash-only discipline.** The process must tolerate being killed at any phase; recovery is restart, not repair. [reliability.md](reliability.md) makes the side effects safe.

## Consequences

- "Why isn't my service available?" is answerable from phase logs; a hang is attributable to a phase.
- Eager validation trades slower boot for no construction failures mid-request.
- Strategy collection before capability initialization makes a missing policy a boot failure, not a runtime error.
- Cost: every service and plugin must be constructible at boot in every environment, including CI.

## Checks

- Lifespan test: phases log in order; a poisoned factory, an unimportable plugin or a raising hookimpl aborts before `yield`; an enabled feature with an invalid settings slice, or with a required vendor not configured, aborts before `yield` with one `plugin_boot_failed` event naming the key.
- Boot test: under a `socket.connect` spy, startup opens outbound connections only from declared credential checks.
- Boot test: a credential check returning `UNAUTHORIZED` logs `credential_check_failed` at ERROR and one returning `TRANSIENT_ERROR` logs `credential_check_inconclusive` at WARNING; in both cases boot completes and the feature stays registered.
- Boot test: a plugin disabled in configuration is never registered; every extension point is filled before its capability initializes.
- Readiness flips only after `yield`; shutdown completes within budget under test.
- Review: no scheduled job runs without a lease.

## Migration

Tickets: TASK-58 (coordination contract and leases), TASK-109 (service registry), TASK-110 (plugin loading), TASK-98 (lazy AssumeRole), TASK-126 (credential checks), TASK-172 (required dependencies abort boot), TASK-128 (directory check).

Tolerated until closed:
- services not yet registered built lazily or in `startup_warmup` hookimpls; phase 2 resolves the registered records and coordination contracts (TASK-109);
- phase 2 builds AWS clients, and with only ambient credentials that contacts the instance metadata endpoint before `yield` (TASK-149);
- network I/O before `yield` that aborts boot on failure: the opt-in directory warmup, and `access/sync`'s AssumeRole during client construction;
- in-process event subscriptions registered in `startup_warmup` by `access/request` and `access/sync`;
- legacy scheduled jobs hand-imported by `jobs/scheduled_tasks.py` (the stale-channel job until TASK-145.9), with leases from the coordination contract;
- legacy `modules/` handlers registered by hand after feature registration;

**Changes:**
- 2026-09-24: phases aligned with plugin-architecture (config-file enablement, registry validation, extension-point collection, multi-replica); `applies` corrected to `target`.
- 2026-09-25: only deploy-coupled defects abort boot; a feature with invalid settings is skipped; boot credential checks alert but never abort; readiness is lifespan completion.
- 2026-10-06: TASK-110 loads plugins from entry points; the filesystem-walk tolerance is closed.
- 2026-10-14: phase 2 runs in the lifespan for the records and coordination contracts, before plugin loading (TASK-109).
- 2026-10-15: the configuration phase validates vendor slices with the host slices; the transport has an enablement key in the configuration files, `SLACK_ENABLED` being its interim form (TASK-153).
- 2026-10-22: the circuit breaker's failure counting follows AWS's two stages; deploys, rollback and its rehearsal are decided in deployment.md (TASK-111.16).
- 2026-10-22: the configuration phase runs in the app factory (`uvicorn --factory`) before the middleware is built; the lifespan receives the loaded configuration (TASK-111.7).
- 2026-10-23: logging is configured first in the configuration phase, right after the identity and `[logging]` slices (TASK-111.17).
- 2026-10-23: the transport's switch is `[slack_transport] enabled`, and its cross-slice rules run in the configuration phase; the `SLACK_ENABLED` tolerated item is closed (TASK-112.1).
- 2026-10-26: the scheduler starting inside the Slack branch is listed as tolerated; phase 6 starts it independent of the transports (TASK-112.4).
- 2026-10-26: `[scheduler] enabled` starts the scheduler after the transports, independent of the Slack app; the stale-channel job uses the Slack Web API client and runs only with `[slack.tenant]`; that tolerated item is closed (TASK-112.4).
- 2026-10-27: a feature with invalid settings or a required vendor not configured aborts boot like every other layer; the degraded starts are JWKS issuer gaps and credential checks only (TASK-172).
- 2026-10-28: the unread directory warmup timeout and preload-group settings are deleted; `[directory] require_startup_warmup` is the one warmup opt-in left, and its removal is TASK-128.
- 2026-10-29: phase 1 ends with the generated `configuration_summary` instead of logging slice keys; plugin slices validate in phase 3, which logs `plugin_configuration_summary` (TASK-156 planning).
