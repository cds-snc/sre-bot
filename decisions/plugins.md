---
status: Accepted
date: 2026-07-06
applies: now
scope: How feature packages register with the host.
---

# Plugins

## Context

Features attach handlers (Slack, HTTP, jobs, i18n resources) to the host at startup. pluggy provides hookspec/hookimpl registration and is already in use. The old record chose entry-points discovery, but that requires the app to be an installed distribution with an importable package root — a packaging change we have deliberately not made ([toolchain.md](toolchain.md)); the code implements a filesystem walk. This record blesses reality.

## Decision

**pluggy, confined to startup.** Hookspecs are host-owned, defined centrally in `app/infrastructure/plugins/specs.py`; adding one is a reviewed change. Hooks fire during lifespan phases to *register* things; nothing pluggy runs on the request path — FastAPI `Depends` owns that, and the two never compete.

**Discovery: filesystem walk over `app/packages/`** (`auto_discover_plugins`). Simple, right for a first-party monolith with a flat layout. Entry-points discovery is re-considered only if we ever ship features as separate distributions — a requirement nobody has established. `app/modules/` remains in the walk only until [migration.md](migration.md) removes it.

**Plugin granularity:** each package under `app/packages/` that defines hookimpls in its `__init__.py` is a plugin. A complex feature (like `access`) may register its subdomains as separate plugins, provided they live under the feature's directory and share its settings namespace — the shipped shape is fine; the old "umbrella-only" rule is dropped.

**Hookimpl signatures** may receive the platform's runtime context where the platform requires it (the FastAPI app for route mounting, the Bolt app for listener attachment). The purity rule is scoped honestly: *cross-platform* hookspecs (i18n, jobs) take Protocols and value types only.

**Feature flags:** `pm.set_blocked(name)` before load, driven by settings.

**Marker discipline:** features import `hookimpl` from `infrastructure.plugins`, never from `pluggy` directly (already implemented — keep it).

## Consequences

- New feature = new directory + hookimpls; no registration lists to edit (the legacy hard-coded list in `lifespan.py` dies with the migration).
- Tolerated until the lifespan cleanup ticket closes: `app/server/lifespan.py` imports `pluggy.PluginManager` directly (host plumbing predating the re-export rule).
- We keep pluggy for its ergonomics while acknowledging a Protocol-plus-list would also have worked; the switching cost isn't worth paying in either direction now.
- Registry is frozen after startup: hooks never fire per-event ([platform-transports.md](platform-transports.md)).

## Checks

- No `import pluggy` outside `app/infrastructure/plugins/` (tolerated: `app/server/lifespan.py` until its cleanup ticket closes).
- Discovery paths contain only `packages` (plus `modules` until migration completes).
- Boot fails loudly on a plugin import error (test with a poisoned package).
