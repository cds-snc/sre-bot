---
title: "Plugin Registration and Discovery"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [plugins, architecture]
constrained_by: [layered-architecture.md, application-lifecycle.md, package-management.md, project-metadata.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Plugin Registration and Discovery

## Context and Problem Statement

The application uses a plugin framework — Pluggy — to let domain features extend the host's behavior at well-defined integration points (route registration, transport handlers, background-job declaration, internationalization resources, event subscriptions, startup warmup). The host owns a small set of versioned hook specifications (the contracts); features ship hook implementations (the behavior). The framework calls implementations on the host's behalf at lifespan time.

The problem this record addresses: **how does the host application discover its plugins, and how is each plugin registered, named, and structured as a Pluggy namespace?** The answer determines:

1. Where the list of plugins lives — declarative metadata in `pyproject.toml`, an explicit list in code, or implicit filesystem scan — and therefore how a contributor adds a new feature plugin to the application.
2. The granularity of a plugin — one feature package per plugin, one capability per plugin, or one module per plugin — and therefore how Pluggy sees the application's structure.
3. The marker namespace name and how it relates to the project distribution name, which controls hookspec/hookimpl coupling.
4. When discovery and registration happen during the application's lifespan, and what happens if a plugin fails to load.

**Constraints:**

- The host is a single Python application installed from this repository; "first-party" plugins (the application's own feature packages) and "third-party" plugins (separately distributed packages that extend the host) are both possible. Discovery must accommodate both.
- Dependency declaration and project metadata live in `pyproject.toml` (PEP 621 / PEP 735). Tool configuration co-locates there. Whichever discovery mechanism is chosen must align with that file's role as the project's metadata surface.
- Plugin registration runs inside the host's lifespan, before transports bind. The framework's registries are frozen after the lifespan yield; hooks are not registered or unregistered on a running process.
- Pluggy is the chosen plugin framework; this record specifies how plugins are *registered with* and *discovered by* a Pluggy `PluginManager` instance, not the choice of framework itself.

**Non-goals:**

- This record does not enumerate the application's hookspec catalogue (the specific hooks: `register_routes`, `register_slack_commands`, etc.). Each hookspec is added through normal review when the integration point is justified.
- This record does not pick the internal layout of a feature plugin (where its services, routes, and adapters live). It specifies what Pluggy *sees* — the namespace it registers — not what lives inside that namespace.
- This record does not pick the lifespan-phase mechanics (when the plugin manager is constructed, where hookspecs are added). Those are owned by the lifespan record; this record names the registration *technique*.
- This record does not specify hookspec signatures or `firstresult` semantics on a per-hook basis; those are decisions tied to each hookspec when it is introduced.

## Considered Options

**Option 1 — Entry-points discovery via `pyproject.toml`.** Each plugin declares itself under `[project.entry-points."<host_namespace>"]` in `pyproject.toml` (first-party) or in a separately distributed package's metadata (third-party). The host calls `pm.load_setuptools_entrypoints("<host_namespace>")` once at startup and Pluggy resolves and registers every entry-point target. The list of plugins is declarative metadata, version-controlled, and identical for first-party and third-party.

**Option 2 — Explicit manual registration.** A composition-root module imports each plugin module and calls `pm.register(plugin_module)` once per plugin. The list of plugins is a literal Python list in code. Adding a new feature requires editing the composition-root file. Third-party plugins require a separate mechanism (or are not supported).

**Option 3 — Filesystem walk.** At startup, the host walks `app/packages/` (or an equivalent directory), imports each top-level subpackage, and registers it. The list of plugins is implicit in the filesystem. Adding a new feature requires only creating the directory; no metadata edit is needed. Third-party plugins require a separate mechanism.

**Option 4 — Hybrid: filesystem walk for first-party + entry-points for third-party.** First-party plugins are discovered by walking `app/packages/`; third-party plugins use entry-points. Two registration mechanisms run in sequence. This mirrors pytest's split (built-in plugins live inside `_pytest/`; external plugins use entry-points).

## Decision Outcome

**Chosen: Option 1 — entry-points discovery via `pyproject.toml`.**

Entry-points are the standardized Python packaging mechanism for "advertising" components from one distribution to another. Pluggy supports them natively via `pm.load_setuptools_entrypoints()`. They give the application **one discovery mechanism for first-party and third-party plugins alike**, with the plugin list expressed as declarative metadata that is version-controlled, reviewable, and visible at the same place where dependencies and project metadata live. The alternative options either require a separate code-edit step per plugin (Option 2), implicit filesystem semantics (Option 3), or a two-mechanism setup (Option 4); none of those benefits outweigh the simplicity of one declarative list per distribution.

### Marker namespace

The host application chooses a single marker namespace name. By convention it equals the project's distribution name as declared in `pyproject.toml [project] name`. The same name is used three places:

1. The `HookspecMarker` and `HookimplMarker` instances at the framework level: `HookspecMarker("<host_namespace>")`, `HookimplMarker("<host_namespace>")`.
2. The `PluginManager` constructor: `pluggy.PluginManager("<host_namespace>")`.
3. The entry-point group name: `[project.entry-points."<host_namespace>"]`.

Using the project's distribution name as the marker namespace is Pluggy's documented convention. It guarantees that a plugin's `@hookimpl` decorator binds to this host's hookspecs only, not to a different host that happens to use the same hook names.

### Plugin = one feature package = one entry point

Pluggy defines a plugin as "a namespace type (currently one of a class or module) which defines a set of hook functions." This codebase pins that definition: **each plugin is a Python module — specifically, a feature package's `__init__.py`** — and **each feature package is exactly one plugin**.

- A feature package corresponds to a single product capability and exposes one set of hookimpls. Sub-capabilities of a complex feature are not separate plugins; they are internal structure of the feature plugin. Pluggy sees one namespace per feature.
- Each plugin declares one entry-point line in `pyproject.toml`:

  ```toml
  [project.entry-points."<host_namespace>"]
  <feature_name> = "app.packages.<feature_name>"
  ```

  The entry-point name is the feature's package name; the object reference is the package's import path. Pluggy resolves the reference via `importlib.import_module()` and registers the resulting module object as the plugin.

- Third-party plugins follow the same shape. A separately distributed package declares `[project.entry-points."<host_namespace>"]` in its own `pyproject.toml`; once installed into the runtime environment, Pluggy discovers it through the same `load_setuptools_entrypoints()` call.

### Hookspec ownership and location

Hookspecs are versioned contracts owned by the host. They are not owned by individual features:

- Hookspecs live at the framework level of the host application, not inside any feature package. The exact module path is a lifespan/composition concern; what this record fixes is that hookspecs are centralized — one canonical module — so the contract surface is small and reviewable.
- Adding a new hookspec is a deliberate change: a new integration point in the host's plugin contract. It is paired with the documentation (signature, semantics, `firstresult` if applicable, return-type expectations) and goes through normal review. Removing a hookspec is governance-grade because it breaks every plugin that implements it.
- Hookspec parameters use Protocol or value types from the type-boundaries decision; they do not pass concrete vendor types or infrastructure-implementation classes through the plugin contract.

### Registration sequence at startup

Plugin discovery and registration happen during the dedicated phase of the lifespan owned by the host. The sequence is:

1. The host constructs a `pluggy.PluginManager("<host_namespace>")`.
2. The host calls `pm.add_hookspecs(<host_hookspec_module_or_class>)` to register the contract.
3. The host applies feature-flag-based blocking (see "Conditional registration" below) by calling `pm.set_blocked(<feature_name>)` for any plugin the host has decided not to load this run.
4. The host calls `pm.load_setuptools_entrypoints("<host_namespace>")`. Pluggy enumerates every entry point in the `<host_namespace>` group, imports each target module, and registers it as a plugin (skipping any name that has been blocked).
5. The host calls each hook (`pm.hook.register_routes(app=...)`, `pm.hook.startup_warmup(...)`, etc.) in the order documented by the lifespan record. Each call invokes every registered plugin's matching hookimpl.

Once the lifespan yields, the plugin manager's registry is frozen. No plugin is registered, blocked, or unregistered after the application begins serving traffic.

### Conditional registration (feature flags)

A feature whose required runtime configuration is missing — or whose feature-flag setting is `false` — is excluded from the plugin set, not partially activated. The mechanism:

- The host evaluates feature-flag settings during the configuration phase of the lifespan (before plugin discovery).
- For each feature whose flag is `false`, the host calls `pm.set_blocked("<feature_name>")` before `load_setuptools_entrypoints()`. Pluggy then refuses to register the entry point even though it is declared in metadata.
- This is preferred over conditional logic *inside* a hookimpl, because a blocked feature consumes no resources, registers no routes (so they do not appear in OpenAPI), and reads no further settings.

A feature that is *enabled but partially gated* (some sub-capabilities on, others off) handles the partial gating inside its own hookimpls — that is internal to the feature, not a host concern. The host's responsibility is binary: load or block.

### Hookimpl options

The application uses Pluggy's hookimpl options sparingly and only when a hookspec's documented semantics require them:

- `tryfirst` / `trylast` — ordering between hookimpls. Used when the hookspec calls for a specific ordering across plugins (e.g., a base translation set must register before feature translations override entries). The hookspec documents the expectation; the hookimpl marks itself accordingly.
- `wrapper` (new-style) — pre/post wrapping of the hookimpl chain via a generator that yields. Used when a hookspec needs cross-cutting before/after behaviour without each plugin paying the cost.
- `optionalhook` — a hookimpl that does not have a corresponding hookspec is rejected by default. `optionalhook=True` opts a feature out of that strictness; used only when a feature ships an implementation for a hookspec that may or may not be present (rare).
- `specname` — overrides the binding from function name to hookspec name. Used only when one feature must implement a hookspec from a name-conflicting situation; rare.

`hookwrapper` (the legacy wrapper marker) is not used in new code; new wrappers use `wrapper`.

### Failure semantics

A plugin that fails to load fails the application boot:

- An entry-point target that cannot be imported (`ImportError`, `ModuleNotFoundError`) raises during `load_setuptools_entrypoints()`. The host does not catch and continue; startup terminates. The error message names the entry-point and the underlying import failure.
- A hookimpl that raises during a hook call (e.g., `register_routes`) propagates the exception out of `pm.hook.<name>()`. The host treats this as a startup failure and terminates the lifespan.
- The "explicit, upfront registration" guidance from the Pluggy ecosystem is followed: every plugin's load and every hookimpl's first call happen at startup, and any failure there is fatal. This makes the running application's plugin set a known invariant rather than a partial-success collection.

## Consequences

**Positive:**

- The plugin list is declarative metadata: one line in `pyproject.toml` per feature, version-controlled and reviewable. Adding a feature is a metadata edit, not a code edit at the composition root.
- First-party and third-party plugins use one mechanism. A future plugin distributed as a separate package integrates with no special handling.
- Pluggy's entry-point integration is documented, stable, and used at scale by pytest, datasette, and other Pluggy-based projects. The mechanism is not project-novel.
- Feature-flag gating lives at one well-defined moment (`pm.set_blocked()` before `load_setuptools_entrypoints()`), and a blocked feature is genuinely absent — not partially activated.
- The marker-namespace = project-name rule prevents accidental cross-host hookimpl registration if a third-party plugin links against a similarly named hookspec from a different ecosystem.

**Tradeoffs accepted:**

- A new feature requires an entry-point declaration in `pyproject.toml`. This is one extra line per feature; the cost is paid once per feature, not per change to the feature.
- Entry-points are loaded eagerly at startup (every entry point's target is imported). For very large plugin sets this could affect startup time. The mitigation is bounded by the host's actual plugin count, which is small for a single-application monolith; it would be reconsidered only if the count grew into the dozens-of-large-modules range.
- The `pluggy.PluginManager` is host-state — its registry must be reachable from the lifespan and from the hookimpl-call sites. The injection / location pattern is established by the lifespan record; this record only requires that the manager exists at exactly one location per running process.

**Risks:**

- A feature is added to `app/packages/` but its entry-point is forgotten in `pyproject.toml`; the feature is dead code. Mitigation: code review; the new-feature checklist names the entry-point edit as a required step. Optionally, a CI check enumerates `app/packages/` subdirectories and confirms each has a matching entry-point line.
- A blocked feature's entry-point declaration grows stale (the feature has been removed but the metadata line remains). Mitigation: removing a feature includes deleting its entry-point line; PR review enforces it.
- A third-party plugin registers hookimpls under the host's namespace inadvertently (e.g., the third-party package mistakenly uses the host's name). Mitigation: Pluggy's marker-namespace check rejects mismatched markers; the host's namespace is documented and stable.

## Confirmation

Compliance is verified by:

- **Repository contents.** `pyproject.toml` contains a `[project.entry-points."<host_namespace>"]` section with one line per feature plugin. The `<host_namespace>` value matches the project's `[project] name`. No code path uses `pm.register(<feature_module>)` for a first-party feature outside of test fixtures.
- **Host code.** Exactly one `pluggy.PluginManager(...)` is constructed in the application per running process. The construction, `add_hookspecs` call, optional `set_blocked` calls, and `load_setuptools_entrypoints` call live at the lifespan's plugin-discovery phase.
- **Marker namespaces.** The `HookspecMarker` and `HookimplMarker` initialization in framework code use the project distribution name. Feature hookimpls use the same `HookimplMarker` import (re-exported by the host's framework module).
- **Code review.** A PR adding a feature includes the `pyproject.toml` entry-point line. A PR adding a hookspec includes the contract documentation (signature, `firstresult` choice, return semantics) and rationale.
- **CI step.** The application's startup-time integration test (or a dedicated boot test) constructs the `PluginManager`, calls `load_setuptools_entrypoints("<host_namespace>")`, and asserts that every expected first-party feature is registered. A missing entry-point manifests as a test failure, not a runtime surprise.

## Source References

1. Pluggy — Official Documentation
   - URL: <https://pluggy.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Defines Pluggy's core concepts (host application, plugin, hookspec, hookimpl, `PluginManager`), the canonical lifecycle (define hookspecs → register plugins → call hooks), and the documented distinction between manual `pm.register()` and `pm.load_setuptools_entrypoints()`. Establishes that "a plugin is a namespace type (currently one of a class or module)." Grounds the choice of entry-points-based discovery and the rule that plugins are modules.

2. Pluggy — Marker Namespace Convention
   - URL: <https://pluggy.readthedocs.io/en/stable/index.html#a-toy-example>
   - Accessed: 2026-05-08
   - Relevance: Documents that `HookspecMarker` and `HookimplMarker` "must be initialized with the name of the host project (the `name` parameter in `setup()`)." Grounds the rule that the marker namespace equals the project's distribution name from `pyproject.toml [project] name`.

3. Pluggy — Hookimpl Options
   - URL: <https://pluggy.readthedocs.io/en/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents the hookimpl options (`tryfirst`, `trylast`, `wrapper`, `hookwrapper` legacy, `optionalhook`, `specname`), `firstresult` semantics on hookspecs, and the `set_blocked()` / `is_blocked()` API. Grounds the conditional-registration rule and the hookimpl-options policy.

4. Python Packaging — Entry Points Specification
   - URL: <https://packaging.python.org/en/latest/specifications/entry-points/>
   - Accessed: 2026-05-08
   - Relevance: Defines entry points as the standardized discovery mechanism for "installed distributions to advertise components for use by other code," with three properties (group, name, object reference). Establishes the canonical use case as plugin discovery and the `importlib.metadata.entry_points()` runtime API. Grounds the choice of entry-points as the registration mechanism and the `[project.entry-points."<group>"]` declaration shape.

5. pytest — Writing Plugins
   - URL: <https://docs.pytest.org/en/stable/how-to/writing_plugins.html>
   - Accessed: 2026-05-08
   - Relevance: Documents pytest's pattern as the canonical Pluggy-based plugin host. Establishes that distributed plugins are declared via `[project.entry-points.pytest11]` in `pyproject.toml`, that "explicit, upfront registration" is the recommended posture (dynamic management is discouraged), and that plugins live for the process lifetime. Grounds the entry-points rule, the fail-fast registration policy, and the no-runtime-unregister rule.

6. Python Packaging — pyproject.toml Project Table
   - URL: <https://packaging.python.org/en/latest/specifications/pyproject-toml/>
   - Accessed: 2026-05-08
   - Relevance: Documents `[project]` and `[project.entry-points]` tables in `pyproject.toml` as the standard declarative location for entry-point group declarations. Grounds the file location and TOML key shape used for feature-plugin entries in this record.

## Change Log

- 2026-05-08: Created. Establishes Pluggy entry-points discovery via `pyproject.toml [project.entry-points."<host_namespace>"]` as the single registration mechanism for both first-party and third-party plugins. Pins one feature package = one plugin = one entry point, with the feature's `__init__.py` registered as the namespace. Names the project distribution name as the canonical marker-namespace value. Names `pm.set_blocked()` as the feature-flag mechanism applied before `load_setuptools_entrypoints()`. Establishes fail-fast registration semantics (an unimportable entry-point or a raising hookimpl terminates the lifespan). Centralizes hookspec ownership at the host level and treats new-hookspec introduction as a deliberate review-gated change. Hookimpl options are used only when the hookspec's documented semantics call for them; `wrapper` replaces legacy `hookwrapper` in new code.
