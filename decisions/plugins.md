---
status: Accepted
date: 2026-07-08
applies: target
scope: How feature packages register with the host.
---

# Plugins

## Context

Features attach handlers (Slack, HTTP, jobs, i18n resources) to the host at startup. pluggy provides hookspec/hookimpl registration and is already in use. pluggy offers exactly two ways to register a plugin: explicit `pm.register(module)` and `pm.load_setuptools_entrypoints(group)`, which enumerates entry points declared in installed distributions. It offers no filesystem-scan primitive; a directory walk is a project invention.

The shipped code walks `app/packages/` with `pkgutil.walk_packages`, imports every subpackage, and registers it — and it catches import errors and *continues*, so a broken feature silently fails to load. That is implicit registration (any directory on disk is a plugin) and it is not fail-fast. It contradicts the intent recorded when this system was designed: **which plugins load should be a declarative, reviewed statement, not a side effect of what happens to sit in a folder.** A prior revision of this record blessed the walk as "reality"; that was the wrong call — it optimized for zero-config over intent and diverged from how every mature pluggy host (pytest, datasette, tox) actually works. This record restores the intended design and supersedes that revision.

## Decision

**pluggy, confined to startup.** Hookspecs are host-owned, defined centrally in `app/infrastructure/plugins/specs.py`; adding one is a reviewed change. Hooks fire during lifespan phases to *register* things; nothing pluggy runs on the request path — FastAPI `Depends` owns that, and the two never compete.

**Discovery: entry-points declared in `pyproject.toml`.** Each feature advertises itself under `[project.entry-points."<marker_namespace>"]`; the host calls `pm.load_setuptools_entrypoints("<marker_namespace>")` once, in the plugin-discovery phase of the lifespan. The plugin set is declarative metadata — version-controlled, reviewable in one place, and the same mechanism for first-party features and any future third-party distribution. The filesystem walk (`auto_discover_plugins`) is removed.

```toml
[project.entry-points."sre_bot"]
access    = "packages.access"
geolocate = "packages.geolocate"
```

This is why pytest — the canonical pluggy host — uses an explicit builtin list plus the `pytest11` entry-point group, never a scan; declarative registration is the documented pluggy posture.

**Packaging requirement.** `load_setuptools_entrypoints` reads installed-distribution metadata (`importlib.metadata`), so the app must be installed as a distribution for its own entry points to resolve — editable (`uv sync`) in dev, non-editable in the image. [toolchain.md](toolchain.md)'s uv workflow already installs the project, so this needs no new packaging posture; it is a footgun only if someone runs from bare source without syncing, which loads zero plugins and must fail loudly (see Checks). Entry-point object references use the repo's **flat import names** (`packages.<feature>`, not `app.packages.<feature>`); this is orthogonal to and compatible with the deferred `app.`-rooted layout in [toolchain.md](toolchain.md) — entry points advertise import paths regardless of the root name.

**Marker / group namespace.** One constant, sourced from project metadata, used in all four places: `HookspecMarker`, `HookimplMarker`, `PluginManager(...)`, and the `[project.entry-points."..."]` group. Reconcile the current split (code uses `sre_bot`; `[project] name` is `sre-bot`) onto that single constant so a plugin's `@hookimpl` binds to this host only.

**Plugin granularity:** each package under `app/packages/` that ships hookimpls is a plugin and declares one entry-point line. A complex feature (like `access`) may register its subdomains as separate plugins, provided they live under the feature's directory and share its settings namespace — each subdomain plugin gets its own entry-point line.

**Hookimpl signatures** may receive the platform's runtime context where the platform requires it (the FastAPI app for route mounting, the Bolt app for listener attachment). The purity rule is scoped honestly: *cross-platform* hookspecs (i18n, jobs) take Protocols and value types only.

**Feature flags:** `pm.set_blocked(name)` before `load_setuptools_entrypoints`, driven by settings. A blocked feature registers nothing — no routes, no OpenAPI entries, no further settings reads.

**Marker discipline:** features import `hookimpl` from `infrastructure.plugins`, never from `pluggy` directly (already implemented — keep it).

**Failure is fatal.** An entry-point target that will not import, or a hookimpl that raises during a hook call, terminates the lifespan. No catch-and-continue: the running app's plugin set is a known invariant, not a partial-success collection. This replaces the current swallow-and-log walk.

## Consequences

- New feature = new directory + hookimpls + **one entry-point line**, reviewed in the PR. Adding a plugin is a declarative metadata edit, not an implicit disk placement. The legacy hard-coded list in `lifespan.py` dies with the migration.
- One mechanism covers first-party and any future separately-distributed plugin; the door the old entry-points ADR opened stays open without extra machinery.
- Cost, accepted: a feature added to `app/packages/` without its entry-point line is dead code. Mitigated by review and a CI check that every `app/packages/` feature has a matching entry point (see Checks).
- Registry is frozen after startup: hooks never fire per-event ([platform-transports.md](platform-transports.md)).
- `app/server/lifespan.py` importing `pluggy.PluginManager` directly is tolerated until its cleanup ticket closes (host plumbing predating the re-export rule).

## Checks

- No `import pluggy` outside `app/infrastructure/plugins/` (tolerated: `app/server/lifespan.py` until its cleanup ticket closes).
- Plugin registration goes through `pm.load_setuptools_entrypoints("<marker_namespace>")`; no `pkgutil`/`walk_packages`-based discovery remains, and `pm.register()` for a first-party feature appears only in test fixtures.
- Boot fails loudly on a plugin import error or a raising hookimpl (test with a poisoned package) — not swallowed.
- A boot test asserts every expected first-party feature is registered; a missing entry-point surfaces as a test failure, not a runtime surprise. A CI check enumerates `app/packages/` and confirms each feature has a matching entry-point line.
- The marker namespace and the entry-point group name are the same constant, sourced from project metadata.

## Migration

Ticket: plugin-registration convergence. Steps: add `[project.entry-points."sre_bot"]` lines for every current feature; replace `auto_discover_plugins` with `load_setuptools_entrypoints` in the discovery phase; make failure fatal; add the boot test and the `app/packages/`-vs-entry-points CI check; reconcile the `sre_bot`/`sre-bot` namespace onto one constant. `app/modules/` keeps its legacy hard-coded registration until [migration.md](migration.md) removes it — it is not migrated to entry points. Tolerated until the ticket closes: the current filesystem walk.
