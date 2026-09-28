---
status: Accepted
date: 2026-07-08
applies: target
scope: How features and capabilities register with the host, and how extension points collect their strategies.
---

# Plugins

## Context

Features and capabilities attach handlers (Slack, HTTP, jobs, i18n resources) and strategies to the host at startup ([plugin-architecture.md](plugin-architecture.md)). pluggy provides hookspec/hookimpl registration and is already in use. It offers two ways to register a plugin: explicit `pm.register(module)` and `pm.load_setuptools_entrypoints(group)`, which reads entry points from installed distribution metadata. It has no filesystem-scan primitive.

Current code:
- `infrastructure/plugins/base.py`'s `auto_discover_plugins` walks `packages/` and `modules/` with `pkgutil.walk_packages`, imports every subpackage and registers it. It logs and skips a package that fails to import, so a broken feature silently does not load.
- A `startup_warmup` hookimpl that raises aborts boot. `access/sync`'s warmup assumes an AWS role through STS, so a business feature's credentials failure stops the whole app.
- `pyproject.toml` declares no entry points.
- Hookspecs live in `infrastructure/plugins/specs.py`: `register_slack_commands`, `register_slack_listeners`, `register_routes`, `register_i18n_resources`, `register_event_handlers`, `register_background_jobs`, `startup_warmup`.
- `register_event_handlers` has no implementations. `access/request` and `access/sync` subscribe to the blinker-backed dispatcher by calling `register_handler` inside `startup_warmup`.
- The marker name is `"sre_bot"` in code; `[project] name` is `sre-bot`. `server/lifespan.py` imports `pluggy.PluginManager` directly.

Which plugins load should be a reviewed statement, not a side effect of what sits in a folder. Every mature pluggy host (pytest, datasette, tox) uses a declared list or entry points, never a scan.

## Decision

**pluggy, confined to startup.** Hooks fire only during lifespan ([lifecycle.md](lifecycle.md)) to register handlers and collect strategies. Nothing pluggy runs on the request path; pluggy hooks are synchronous and are never called per request.

**Hookspecs are public API.** The host's registration hookspecs and extension points live in `contracts/`. A capability's extension points live in its own hookspecs module. Adding or changing a hookspec is a reviewed change that follows [hookspec-deprecation.md](hookspec-deprecation.md).

**Discovery: entry points declared in `pyproject.toml`.** Each feature and each capability declares one entry point per plugin module under the host's group. Capabilities register exactly like features.

```toml
[project.entry-points."sre_bot"]
"access.request" = "features.access.request"
"incident.draft" = "features.incident.draft"
approvals        = "capabilities.approvals"
```

Entry-point names are dotted `<package>.<subdomain>` for subdomains, so the flat per-group name registry cannot collide. An umbrella feature's own package holds no hookimpls and is never an entry point ([feature-packages.md](feature-packages.md)).

**Enablement comes from configuration.** Each entry point has an enablement key in the base configuration file; the environment's file may override it ([configuration.md](configuration.md)). The host reads the entry points, skips every plugin disabled in the environment's configuration before registering it (`pm.set_blocked(name)` or filtering the entry-point list), and registers the rest. A disabled plugin registers nothing: no routes, no OpenAPI entries, no strategies, no settings reads.

**Extension points collect strategies at startup.** For each capability, in its declared order, the host calls that capability's hookspecs once, collects the returned strategy objects, and passes them to the capability before it initializes. At runtime the capability awaits the strategies' async methods. A plugin reacts to something in another package only through such an extension point, or through a queue contract when the reaction must reach every replica or survive a restart. The in-process event dispatcher and the `register_event_handlers` hookspec are not a supported mechanism.

**Packaging requirement.** `load_setuptools_entrypoints` reads installed-distribution metadata, so the app must be installed as a distribution: editable (`uv sync`) in development, non-editable in the image ([toolchain.md](toolchain.md)). Running from bare source without syncing loads zero plugins and must fail loudly. Entry-point targets use the flat import names (`features.<feature>`, not `app.features.<feature>`).

**One namespace constant.** A single constant, sourced from project metadata, names the `HookspecMarker`, the `HookimplMarker`, the `PluginManager` and the entry-point group, so a plugin's `@hookimpl` binds to this host only.

**Credential checks are an opt-in hook.** A feature or capability that depends on a credential may implement `register_credential_checks`, returning checks as value types (a name and an async callable that returns `OperationResult`). The host runs them once, concurrently, after registration, and logs a failure at ERROR without aborting boot or unregistering the plugin ([lifecycle.md](lifecycle.md)). Plugins that don't implement the hook make no network call at boot.

**Hookimpl signatures** may receive a platform runtime object where the platform requires it (the FastAPI app for routes, the Bolt app for listeners). Cross-platform hookspecs (i18n, jobs, extension points) take contracts and value types only. Recurring jobs attach only through `register_background_jobs`, carrying schedule, tier and lease TTL as value types; the host never imports a feature's job body directly ([reliability.md](reliability.md)).

**Marker discipline.** Plugins import `hookimpl` from `contracts`, never from `pluggy` directly.

**Boot failure policy is fixed by layer and kind of failure.** It follows [lifecycle.md](lifecycle.md)'s rule that only deploy-coupled defects abort boot:

| Failure | Host, capability | Feature |
| --- | --- | --- |
| Entry-point target will not import, or a hookimpl raises during startup | abort | abort |
| Settings slice fails validation | abort | skip the plugin |
| Credential check fails | log ERROR, keep serving | log ERROR, keep serving |

Code defects abort in every layer: they ship with the image, the old tasks keep serving during the deploy, and rollback fixes them. A skipped feature registers nothing (the host drops what it registered before the registries freeze), and the host logs one CRITICAL `plugin_boot_failed` event naming the plugin, phase and error type ([observability.md](observability.md)). Capabilities and host services abort instead of being skipped because features depend on them. There is no per-plugin override. Backstage offers one (`onPluginBootFailure`, [building backends](https://backstage.io/docs/backend-system/building-backends/index/)); we keep a single policy instead, so a feature cannot opt into taking the whole app down.

## Consequences

- A new feature or capability is a directory, hookimpls, one entry-point line and one enablement key, all reviewed in the PR.
- The same mechanism serves first-party packages and any future separately distributed plugin.
- Cost: a package without its entry-point line is dead code. The boot test and the CI check below catch it.
- Registries freeze after startup; hooks never fire per event ([platform-transports.md](platform-transports.md)).

## Checks

- Plugin registration goes through `pm.load_setuptools_entrypoints`; no `pkgutil`/`walk_packages` discovery remains, and `pm.register()` for a first-party plugin appears only in test fixtures.
- No `import pluggy` outside `contracts/` and the host's plugin manager in `server/`.
- Boot test: a plugin's `register_credential_checks` check returning `UNAUTHORIZED` logs `credential_check_failed` and the plugin still serves; a plugin without the hook opens no connection at boot.
- Boot test: a poisoned package or a raising hookimpl aborts boot in every layer; a feature with an invalid settings slice is absent from every registry and from the OpenAPI schema, `plugin_boot_failed` is logged at CRITICAL, and the other plugins serve; a capability with an invalid settings slice aborts boot.
- Boot test: every expected plugin is registered; every entry point has an enablement key in the base configuration file; a disabled plugin is never registered.
- CI check: every package under `features/` and `capabilities/` that ships hookimpls has a matching entry-point line.
- The marker namespace and the entry-point group are the same constant, sourced from project metadata.
- grep: no new `register_event_handlers` hookimpl or `register_handler` call.

## Migration

Tickets: TASK-18 (contracts, including hookspecs), TASK-110 (entry-point loading), TASK-112 (enablement from configuration), TASK-126 (feature isolation and credential checks). The package moves are listed in [plugin-architecture.md](plugin-architecture.md). `modules/` keeps its hand-written registration until each surface is rebuilt ([migration.md](migration.md)).

Tolerated until closed:
- the filesystem walk in `auto_discover_plugins`, with import errors logged and skipped;
- a raising `startup_warmup` hookimpl aborts boot even when the cause is a feature's settings or credentials;
- hookspecs and the `hookimpl` marker in `infrastructure/plugins/`;
- the `register_event_handlers` hookspec, and `access/request` and `access/sync` subscribing to the in-process dispatcher in `startup_warmup`;
- plugins under `packages/` rather than `features/`;
- the `sre_bot`/`sre-bot` split, and `server/lifespan.py` importing `pluggy.PluginManager`.

**Changes:**
- 2026-09-24: entry points target `features.*` and `capabilities.*`; enablement comes from configuration files; extension points replace the in-process event hook.
- 2026-09-25: boot failure policy is fixed by layer and kind (code defects abort, a feature with invalid settings is skipped); credential checks are an opt-in `register_credential_checks` hook that alerts without aborting.
