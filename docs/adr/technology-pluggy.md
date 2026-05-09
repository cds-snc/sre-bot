---
title: "Technology Selection: Pluggy"
status: Accepted
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [plugins, architecture]
constrained_by: [plugin-registration-discovery.md, layered-architecture.md, package-management.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Technology Selection: Pluggy

## Context and Problem Statement

The plugin registration and discovery standard ([plugin-registration-discovery.md](plugin-registration-discovery.md)) defines the application's plugin contract: a single host process, one feature package per plugin, declarative discovery via `pyproject.toml` entry-points, fail-fast registration at lifespan time, frozen registries after lifespan yield, and a versioned hookspec catalogue owned by the host. The standard does not pick the framework that backs this contract; it leaves the seam at the plugin manager.

The problem this record addresses: **which Python library does the application use as its plugin framework, and on what grounds?** A purpose-built plugin framework is preferred over a hand-rolled registry: hookspec/hookimpl matching, `firstresult` semantics, marker-namespace isolation, blocking/skipping, and entry-point loading are subtle and worth not re-implementing. The selection criteria are:

1. **Fit with the standard's contract** — the framework must expose primitives the application uses directly (hookspec markers, hookimpl markers, plugin manager, entry-point loading, marker-namespace isolation). The application does not wrap them behind a facade; the contract *is* the framework's surface.
2. **Stewardship and maturity** — the framework is maintained, packaged on PyPI, used at scale by other open-source projects whose lifecycle resembles ours.
3. **Documented composition with PEP 621 entry-points** — declarative discovery is a hard requirement of the standard, and the framework must support it without glue.
4. **Tier-2 economics** — per [package-management.md](package-management.md), a small, focused library beats a hand-rolled component.

**Constraints:**

- Unlike the event-dispatch facade (whose backing library is hidden), the plugin framework's surface *is* the application's plugin model. The framework markers (`HookspecMarker`, `HookimplMarker`) and manager (`PluginManager`) are imported by the host's framework module and re-exported for hookimpl authors. Substitution is a higher-cost change than for a faceted library.
- The framework must be importable on the application's Python version (3.13) with stable wheel availability. Native compilation on install is tolerated but not preferred.
- The framework must permit explicit blocking of plugins at registration time (`set_blocked` or equivalent) to support feature-flag-driven exclusion.

**Non-goals:**

- This record does not redefine any rule from the plugin-registration-discovery standard. Where the framework and the standard appear to disagree, the standard wins; the host's wiring code reconciles.
- This record does not catalogue the application's hookspec set. The hookspec catalogue grows through normal review when integration points are justified.
- This record does not pick a specific minor version. The rule is "current stable on PyPI"; minor-version pinning is a `pyproject.toml` concern.

## Considered Options

**Option 1 — Pluggy.** The plugin framework extracted from pytest's plugin model. Provides `HookspecMarker`, `HookimplMarker`, `PluginManager`, `add_hookspecs`, `register`, `load_setuptools_entrypoints`, `set_blocked`, `firstresult` semantics, hookimpl options (`tryfirst`, `trylast`, `wrapper`, `optionalhook`, `specname`), and marker-namespace isolation. Used by pytest, datasette, tox, devpi, hatch, and other Pluggy-based projects.

**Option 2 — Stevedore (OpenStack).** A plugin/extension manager originally from the OpenStack project. Manages entry-points and plugin lifecycles with a different architectural model (driver/extension manager classes, lazy loading by name).

**Option 3 — Hand-rolled registry over `importlib.metadata.entry_points`.** A custom dictionary-based registry, marker decorators implemented as no-ops or simple metadata stamps, manual entry-point enumeration and import.

**Option 4 — Click's plugin pattern.** Click's CLI plugin idiom (entry-points loaded as Click groups). Limited to CLI scope and does not provide hookspec/hookimpl matching for non-CLI extension points.

## Decision Outcome

**Chosen: Option 1 — Pluggy.**

Pluggy satisfies every selection criterion. The contract surface (`HookspecMarker`, `HookimplMarker`, `PluginManager`, `load_setuptools_entrypoints`, `set_blocked`, `firstresult`) maps one-to-one onto the application's plugin standard; there is no impedance mismatch, no glue layer to maintain. The framework's stewardship under the pytest-dev organization is durable — Pluggy releases are tied to pytest's release cadence and security posture. The `[project.entry-points."<host_namespace>"]` pattern is documented at length and is the path used by the largest Pluggy-based hosts. Stevedore (Option 2) is mature but its driver/extension-manager model is a different abstraction than the host/hookspec model the standard requires; using it would impose a translation layer. Hand-rolling (Option 3) re-implements marker-namespace isolation, hookimpl options, and call-order semantics that are subtle and easy to get wrong. Click's pattern (Option 4) is CLI-shaped and does not address the application's broader extension points.

### What the application uses, and what it does not

The application imports from `pluggy` directly in its plugin-framework module:

- **`pluggy.HookspecMarker(<host_namespace>)`** — used by the host's hookspec module to declare contracts.
- **`pluggy.HookimplMarker(<host_namespace>)`** — re-exported to feature packages so they can decorate hookimpls.
- **`pluggy.PluginManager(<host_namespace>)`** — instantiated once at lifespan phase 3.
- **`pm.add_hookspecs(<host_hookspec_module>)`** — to register the contract.
- **`pm.set_blocked(<plugin_name>)`** — applied once per disabled feature before loading.
- **`pm.load_setuptools_entrypoints(<host_namespace>)`** — invoked once to discover and register first-party and third-party plugins.
- **`pm.hook.<name>(...)`** — called at the documented lifespan moments to dispatch hooks.

The application uses Pluggy's hookimpl options sparingly:

- **`tryfirst` / `trylast`** when a hookspec's documented semantics call for an ordering across plugins.
- **`wrapper`** (new-style) when a hookspec needs cross-cutting before/after behaviour.
- **`optionalhook`** when a plugin ships an implementation for a hookspec that may or may not be present.
- **`specname`** only when name conflicts force a rename.

The application does **not** use:

- **`hookwrapper`** — the legacy wrapper marker. New code uses `wrapper`.
- **`historic`** hooks — the application has no need to replay hook calls to plugins registered after a hook fired; registration is frozen at lifespan yield, so historic semantics are inapplicable.
- **Dynamic registration on a running process** — the standard explicitly forbids it.

### Marker-namespace policy

The marker namespace is the project's distribution name (per [plugin-registration-discovery.md](plugin-registration-discovery.md) and [project-metadata.md](project-metadata.md)). All three places that take the namespace string — the `HookspecMarker`, the `HookimplMarker`, the `PluginManager`, and the `[project.entry-points."<host_namespace>"]` group — use the same constant, sourced from the project metadata.

This is Pluggy's documented convention: `HookspecMarker` and `HookimplMarker` "must be initialized with the name of the host project." It guarantees that a plugin's `@hookimpl` decorator binds to this host's hookspecs only, not to a different host that happens to use the same hook names.

### Library version pinning

`pyproject.toml` requires `pluggy >= 1.5` (the stable release that consolidated `wrapper` semantics and removed the legacy `hookwrapper` migration warning). Minor-version upgrades are managed through the dependency-bump workflow ([package-management.md](package-management.md)); breaking-change releases are reviewed.

### Substitution path

If a future need requires a different plugin framework, the substitution touches more code than for a faceted library because the framework's surface *is* the application's plugin model:

1. The host's framework module replaces `pluggy` imports with the new framework's primitives.
2. The hookspec markers, hookimpl markers, and plugin manager are re-bound to the new framework's equivalents.
3. The lifespan phase 3 wiring (`add_hookspecs`, `set_blocked`, `load_setuptools_entrypoints`) replaces with the new framework's calls.
4. Every feature's `@hookimpl` decorator import migrates.

Because the application re-exports the `HookimplMarker` instance from the host's framework module (rather than letting features import it from `pluggy` directly), step 4 is bounded: features import the marker from the host module, and the host module's import resolves to whichever framework is in use. The substitution is bounded to the host's framework module plus a one-time feature import update.

### Pros and cons of the options

**Pluggy.** Good: surface maps directly to the standard; stewardship under pytest-dev; entry-point integration is documented and used at scale; small, focused dependency. Bad: less code than a wrapper would be (acceptable; the standard *is* the framework's contract).

**Stevedore.** Good: mature; OpenStack stewardship. Bad: driver/extension-manager model differs from hookspec/hookimpl; using it imposes a translation layer; less precedent in pytest-style hosts.

**Hand-rolled.** Good: no dependency. Bad: re-implements marker-namespace isolation, hookimpl options, call ordering, and entry-point loading; ongoing maintenance cost on subtle code; correctness regressions in plugin plumbing are easy to introduce and hard to detect.

**Click's plugin pattern.** Good: zero dependency cost if Click is already used. Bad: CLI-shaped; does not address non-CLI extension points (route registration, transport handlers, background-job declaration); unfit for the standard's scope.

## Consequences

**Positive:**

- Pluggy's surface is the application's plugin contract. There is no facade to maintain; the framework is the model.
- Stewardship under pytest-dev is durable; security and bug-fix updates flow through the same channel as pytest updates.
- Entry-point integration via `load_setuptools_entrypoints` is documented and battle-tested by the largest Pluggy host (pytest itself).
- The host's framework module is a one-stop import for hookimpl authors; substitution stays bounded to that module plus the one-line feature import.

**Tradeoffs accepted:**

- The application's plugin code uses Pluggy's idioms directly. A future migration is more involved than swapping a faceted library. Acceptable: the alternative is a wrapper that adds nothing — Pluggy's surface is well-shaped already.
- Hookimpl options (`tryfirst`, `trylast`, etc.) are a vocabulary plugin authors must learn. Acceptable: the standard names which options are permitted; review enforces.

**Risks and mitigations:**

- **A future Pluggy release changes `wrapper` semantics or `firstresult` behaviour.** *Mitigation:* the host's plugin tests cover the application's actual hook call patterns; a breaking-change release is reviewed before bump.
- **A feature uses a hookimpl option not listed in the standard.** *Mitigation:* code review enforces the documented option set; the host's framework module re-exports the marker but does not encourage advanced options.

## Confirmation

Compliance is verified by:

- **Code review.** `import pluggy` appears in the host's plugin-framework module. Feature packages import `HookimplMarker` from the host module's re-export, not from `pluggy` directly.
- **Static analysis.** A check forbids `from pluggy import HookimplMarker` in feature code; features import from the host's framework module.
- **Boot test.** A boot test asserts the `PluginManager` is constructed once, `add_hookspecs` is called once, `load_setuptools_entrypoints` is called once, and the expected first-party plugins are registered.
- **Dependency declaration.** `pyproject.toml` declares `pluggy >= 1.5` under the application's runtime dependencies.

## Source References

1. Pluggy — Project README (PyPI)
   - URL: <https://pypi.org/project/pluggy/>
   - Accessed: 2026-05-08
   - Relevance: Establishes Pluggy's stewardship (pytest-dev organization), packaging maturity, and Python version compatibility. Grounds the maturity-and-stewardship selection criterion.

2. Pluggy — Official Documentation
   - URL: <https://pluggy.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents the full surface used by this application: `HookspecMarker`, `HookimplMarker`, `PluginManager`, `add_hookspecs`, `register`, `load_setuptools_entrypoints`, `set_blocked`, `firstresult`, hookimpl options (`tryfirst`, `trylast`, `wrapper`, `optionalhook`, `specname`), and the marker-namespace convention. Grounds every binding the application makes.

3. pytest — Writing Plugins
   - URL: <https://docs.pytest.org/en/stable/how-to/writing_plugins.html>
   - Accessed: 2026-05-08
   - Relevance: Documents pytest's pattern as the canonical Pluggy-based host: `[project.entry-points.pytest11]` declaration, "explicit, upfront registration" posture, plugins live for the process lifetime. Grounds the choice of Pluggy as a battle-tested framework at the scale the application's standard targets.

4. Stevedore — Documentation
   - URL: <https://docs.openstack.org/stevedore/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents Stevedore's driver/extension-manager model. Grounds the rejection of Stevedore on the architectural-fit criterion: the host/hookspec model the application's standard targets is closer to Pluggy's shape than to Stevedore's.

5. Python Packaging — Entry Points Specification
   - URL: <https://packaging.python.org/en/latest/specifications/entry-points/>
   - Accessed: 2026-05-08
   - Relevance: Defines the standardized discovery mechanism (`[project.entry-points.<group>]` in `pyproject.toml`, `importlib.metadata.entry_points()` runtime API). Grounds Pluggy's `load_setuptools_entrypoints` as a thin adapter over the standard, not a custom mechanism.

## Change Log

- 2026-05-08: Created. Selects Pluggy (`>= 1.5`) as the plugin framework backing the application's plugin standard. Documents the framework's surface as the application's plugin model (no facade), the hookimpl options the application permits and excludes, the marker-namespace policy (project distribution name in three places), the version-pin posture, and the substitution path bounded to the host's framework module.
