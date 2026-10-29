---
status: Accepted
date: 2026-10-15
applies: target
scope: How features and capabilities register with the host, and how extension points collect their strategies.
---

# Plugins

## Context

Features and capabilities attach handlers (Slack, HTTP, jobs, i18n resources) and strategies to the host at startup ([plugin-architecture.md](plugin-architecture.md)). pluggy provides hookspec/hookimpl registration and is already in use. It offers two ways to register a plugin: explicit `pm.register(module)` and `pm.load_setuptools_entrypoints(group)`, which reads entry points from installed distribution metadata. It has no filesystem-scan primitive.

Current code:
- `server/plugins/manager.py`'s `load_plugins` registers plugins with `pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)` before i18n collection. A plugin that fails to import aborts boot, and boot also aborts when the group yields no plugin (missing or stale project metadata).
- A `startup_warmup` hookimpl that raises aborts boot. `access/sync`'s warmup assumes an AWS role through STS, so a business feature's credentials failure stops the whole app.
- `pyproject.toml` declares one entry point per `packages/` plugin under `[project.entry-points.sre_bot]`, named `<feature>` or `<feature>.<subdomain>`. A unit test checks the declarations against the packages that ship hookimpls, in both directions.
- Hookspecs live in `contracts/plugins/hookspecs.py`: `register_slack_commands`, `register_routes`, `register_i18n_resources`, `register_event_handlers`, `register_background_jobs`, `startup_warmup`. The `hookspec` and `hookimpl` markers and the namespace constant live in `contracts/plugins/namespace.py`; the plugin manager lives in `server/plugins/`.
- `register_event_handlers` has no implementations. `access/request` and `access/sync` subscribe to the blinker-backed dispatcher by calling `register_handler` inside `startup_warmup`.
- The namespace constant is read from the installed project metadata (`sre-bot`, normalised to `sre_bot`) and names both markers and the `PluginManager`. pluggy is imported only in `contracts/plugins/` and `server/plugins/`.

Which plugins load should be a reviewed statement, not a side effect of what sits in a folder. Every mature pluggy host (pytest, datasette, tox) uses a declared list or entry points, never a scan.

## Decision

**pluggy, confined to startup.** Hooks fire only during lifespan ([lifecycle.md](lifecycle.md)) to register handlers and collect strategies. Nothing pluggy runs on the request path; pluggy hooks are synchronous and are never called per request.

**Hookspecs are public API.** The host's registration hookspecs and extension points live in `contracts/`. A capability's extension points live in its own hookspecs module. Adding or changing a hookspec is a reviewed change that follows [hookspec-deprecation.md](hookspec-deprecation.md).

**Discovery: entry points declared in `pyproject.toml`.** Each feature and each capability declares one entry point per plugin module under the host's group. Capabilities register exactly like features.

```toml
[project.entry-points."sre_bot"]
"access.request" = "features.access.request"
"access.sync"    = "features.access.sync"
approvals        = "capabilities.approvals"
```

Entry-point names are dotted `<package>.<subdomain>` for subdomains, so the flat per-group name registry cannot collide. An umbrella feature's own package, its `core/` and its `common/` hold no hookimpls and are never entry points ([feature-packages.md](feature-packages.md)).

**Enablement comes from configuration.** Each entry point has an enablement key in the base configuration file, in its product area's `[plugins.<area>]` table; the environment's file may override it ([configuration.md](configuration.md)). The host reads the entry points, skips every plugin disabled in the environment's configuration before registering it (`pm.set_blocked(name)` or filtering the entry-point list), and registers the rest. A disabled plugin registers nothing: no routes, no OpenAPI entries, no strategies, no settings reads. A platform transport (Slack Socket Mode or HTTP host) is host code, not a plugin, and has an enablement key in the configuration files too; a transport switched on without its vendor's tenant entry fails boot naming the missing key, and a transport switched off needs no entry. A vendor client is not a plugin and has no key: its tenant entry enables it ([configuration.md](configuration.md)).

**Extension points collect strategies at startup.** For each capability, in its declared order, the host calls that capability's hookspecs once, collects the returned strategy objects, and passes them to the capability before it initializes. At runtime the capability awaits the strategies' async methods. A plugin reacts to something in another package only through such an extension point, or through a queue contract when the reaction must reach every replica or survive a restart. The in-process event dispatcher and the `register_event_handlers` hookspec are not a supported mechanism.

**Packaging requirement.** `load_setuptools_entrypoints` reads installed-distribution metadata, so the app must be installed as a distribution: editable (`uv sync`) in development, non-editable in the image ([toolchain.md](toolchain.md)). Running from bare source without syncing loads zero plugins and must fail loudly. Entry-point targets use the flat import names (`features.<feature>`, not `app.features.<feature>`).

**One namespace constant.** A single constant, sourced from project metadata, names the `HookspecMarker`, the `HookimplMarker`, the `PluginManager` and the entry-point group, so a plugin's `@hookimpl` binds to this host only.

**Credential checks are an opt-in hook.** A feature or capability that depends on a credential may implement `register_credential_checks`, returning checks as value types (a name and an async callable that returns `OperationResult`). The host runs them once, concurrently, after registration, and logs a failure at ERROR without aborting boot or unregistering the plugin ([lifecycle.md](lifecycle.md)). Plugins that don't implement the hook make no network call at boot.

**Hookimpl signatures** may receive a platform runtime object where the platform requires it (the FastAPI app for routes). Slack commands, block actions and view submissions attach through the registrar Protocol and never receive the Bolt app ([platform-entrypoints.md](platform-entrypoints.md) rule 2). Cross-platform hookspecs (i18n, jobs, extension points) take contracts and value types only. Recurring jobs attach only through `register_background_jobs`, carrying schedule, tier and lease TTL as value types; the host never imports a feature's job body directly ([reliability.md](reliability.md)).

**Marker discipline.** Plugins import `hookimpl` from `contracts`, never from `pluggy` directly.

**Boot failure policy is one rule for every layer.** It follows [lifecycle.md](lifecycle.md)'s rule that only deploy-coupled defects abort boot. An enabled plugin states that it must work in this environment, so in the host, a capability or a feature each of these aborts boot: an entry-point target that will not import or a hookimpl that raises during startup; a settings slice that fails validation; a vendor slice that fails validation; a vendor or capability the plugin requires that is not configured. Each ships with the image or the checked-in configuration: the old tasks keep serving during the deploy, and the circuit breaker's rollback fixes it. A credential check that fails logs ERROR and the plugin keeps serving, because credentials change without a deploy and a rollback cannot fix them. A plugin is switched off with its enablement key, never skipped at boot. This is Backstage's default, where any plugin boot failure aborts the backend ([building backends](https://backstage.io/docs/backend-system/building-backends/index/)); there is no per-plugin override, so an enabled plugin is never silently absent. Every abort logs one CRITICAL `plugin_boot_failed` event naming the plugin, phase and error type, and the configuration key when one is at fault ([observability.md](observability.md)).

**A plugin states what it requires through `register_requirements`.** The optional, no-argument hookspec is fired per plugin before any registration hook; the plugin resolves each vendor or capability it requires and raises the typed required-dependency error (from `contracts/plugins/`) naming the configuration key when one is not configured. A dedicated hook keeps requirements explicit and attributable to one plugin, as Backstage declares plugin dependencies at init and fails startup when one does not resolve ([backends](https://backstage.io/docs/backend-system/architecture/backends)) and Django registers system checks at app load whose errors block startup ([system checks](https://docs.djangoproject.com/en/6.0/topics/checks/)). An import failure is attributed to the entry-point name; the plugin is `unknown` only when none can be derived. A plugin that uses a dependency optionally does not state it.

**A plugin states what it requires by resolving it.** While it registers, a plugin resolves each vendor or capability it requires (vendors through the configured-systems read, [workplace-systems.md](workplace-systems.md) rule 3) and raises the `contracts` required-dependency error, naming the configuration key, when one is absent. Spring fails startup the same way when a required constructor dependency is missing, and only an explicitly optional one may be absent ([Spring Boot auto-configuration](https://docs.spring.io/spring-boot/reference/features/developing-auto-configuration.html)). A plugin runs without a dependency only where its ADR designs that state (comms' AI drafting over text generation, [incident-management.md](incident-management.md)): the dependency is then optional, and its absence is reported as unavailable, never as an error. Whether a vendor is required is never its own slice's decision ([configuration.md](configuration.md)).

## Consequences

- A new feature or capability is a directory, hookimpls, one entry-point line and one enablement key, all reviewed in the PR.
- The same mechanism serves first-party packages and any future separately distributed plugin.
- Cost: a package without its entry-point line is dead code. The boot test and the CI check below catch it.
- Registries freeze after startup; hooks never fire per event ([platform-transports.md](platform-transports.md)).

## Checks

- Plugin registration goes through `pm.load_setuptools_entrypoints`; no `pkgutil`/`walk_packages` discovery remains, and `pm.register()` for a first-party plugin appears only in test fixtures.
- No `import pluggy` outside `contracts/` and the host's plugin manager in `server/`.
- Boot test: a plugin's `register_credential_checks` check returning `UNAUTHORIZED` logs `credential_check_failed` and the plugin still serves; a plugin without the hook opens no connection at boot.
- Boot test: a poisoned package or a raising hookimpl aborts boot in every layer; a feature or capability with an invalid settings slice aborts boot before `yield` with one CRITICAL `plugin_boot_failed` event naming the key; an enabled plugin whose `register_requirements` raises aborts boot naming the plugin and the key.
- Boot test: every expected plugin is registered; every entry point has exactly one enablement key in the base configuration file; a disabled plugin is never imported or registered.
- import-linter `protected`: an entry point's module is imported only from inside itself, so the host, the legacy tree and sibling plugins never import a plugin that may be disabled ([plugin-architecture.md](plugin-architecture.md)); the boot test checks the protected list against the entry points.
- CI check: every package under `features/` and `capabilities/` that ships hookimpls has a matching entry-point line.
- CI check (`bin/check_settings_key_ownership.py`): no settings class outside the configuration files declares an `enabled` field (or, without an `env_prefix`, a `<NAME>_enabled` field), and no `ENVIRONMENT` comparison in `server/lifespan.py`, `server/plugins/`, packages, features or `jobs/` decides whether a plugin or the scheduler runs (TASK-112.4).
- The marker namespace and the entry-point group are the same constant, sourced from project metadata.
- grep: no new `register_event_handlers` hookimpl or `register_handler` call.

## Migration

Tickets: TASK-18 (contracts, including hookspecs), TASK-110 (entry-point loading), TASK-112 (enablement from configuration), TASK-126 (credential checks), TASK-172 (required dependencies abort boot). The package moves are listed in [plugin-architecture.md](plugin-architecture.md). `modules/` keeps its hand-written registration until each surface is rebuilt ([migration.md](migration.md)).

Tolerated until closed:
- a raising `startup_warmup` hookimpl aborts boot even when the cause is a feature's credentials (TASK-126);
- Slack, Google and Opsgenie requirements (incident.scribe, oncall_sync, rant, user_rotations) are not stated, pending a rule on how CI satisfies them (a fake tenant or the plugin switched off) and the configured-systems read (TASK-145.5.9); TASK-175, after TASK-172;
- the `register_event_handlers` hookspec, and `access/request` and `access/sync` subscribing to the in-process dispatcher in `startup_warmup`;
- plugins under `packages/` rather than `features/`.

**Changes:**
- 2026-09-24: entry points target `features.*` and `capabilities.*`; enablement comes from configuration files; extension points replace the in-process event hook.
- 2026-09-25: boot failure policy is fixed by layer and kind (code defects abort, a feature with invalid settings is skipped); credential checks are an opt-in `register_credential_checks` hook that alerts without aborting.
- 2026-10-01: an umbrella's `core/` and `common/` are never entry points, per feature-packages.md.
- 2026-10-01: TASK-107 moved the hookspecs, the markers and the namespace constant to `contracts/plugins/` and the plugin manager to `server/plugins/`; `infrastructure/plugins/` is deleted and its two tolerated items are closed.
- 2026-10-06: TASK-110 replaced the filesystem walk with entry-point loading; an import failure now aborts boot, and that tolerated item is closed.
- 2026-10-06: Slack hookimpls attach through the registrar Protocol, never the Bolt app, matching platform-entrypoints.md rule 2 (TASK-140.2).
- 2026-10-15: a platform transport has an enablement key in the configuration files; an invalid vendor slice aborts boot (TASK-153).
- 2026-10-23: enablement keys sit in one `[plugins.<area>]` table per product area; the host blocks disabled names with `pm.set_blocked` before loading the entry points, so a disabled plugin is never imported (TASK-112.2).
- 2026-10-23: `[slack_transport] enabled` replaced `SLACK_ENABLED`; that tolerated item is closed (TASK-112.1).
- 2026-10-26: blocking keeps a disabled plugin unimported only if nothing else imports it, so an import-linter `protected` contract over the entry-point modules enforces it (TASK-112.2; pytest's `-p no:<name>` blocks the same way before loading).
- 2026-10-26: the CI check for environment-variable and `ENVIRONMENT` plugin switches joins the Checks (TASK-112.4); the access switches `ACCESS_*_ENABLED` go in TASK-112.3.
- 2026-10-27: one boot failure policy for every layer: an enabled plugin whose settings fail validation, or whose required vendor or capability is not configured, aborts boot (Backstage's default); a plugin states a requirement by resolving it at registration; a dependency is optional only where the plugin's ADR designs that state; no skip, no per-plugin override (TASK-172).
- 2026-10-29: requirements are stated through the `register_requirements` hookspec, fired per plugin before registration; an import failure is attributed to its entry-point name; the Boot test line no longer describes the old skip of a feature with an invalid slice (TASK-172 planning).
- 2026-10-29: TASK-172 implemented: `register_requirements` fires per plugin after loading, incident.scribe requires `[openai.tenant]`, ci.toml switches scribe off (a guard test fails when a plugin that states a requirement is on in CI), and `plugin_boot_failed` names the setting at fault in a `setting` field (a field named `key` trips CodeQL's clear-text-logging rule); the "no plugin states what it requires" tolerated item is closed.
