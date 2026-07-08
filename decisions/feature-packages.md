---
status: Accepted
date: 2026-07-06
applies: now
scope: Feature package layout and handler discipline — the record most contributors work from.
---

# Feature Packages

## Context

Features live in `app/packages/`, replacing legacy `app/modules/`. The old layout record was a closed filename catalogue that banned names reality needed (no slot for persistence, no `locales/`) and rejected the `interactions/` directory both shipped features then used. A layout standard both features violate on day one is a standard problem, not a feature problem. This record is reconciled with the shipped shape.

## Decision

### Layout

```text
app/packages/<feature>/
├── __init__.py        # hookimpls: the feature's registration surface
├── service.py         # business logic; the only orchestrator
├── domain.py          # frozen dataclasses, enums, invariants (optional)
├── schemas.py         # Pydantic models at trust boundaries (optional)
├── store.py           # persistence via StorageService Protocol (optional)
├── providers.py       # feature-local DI wiring (optional)
├── adapters/          # Path B adapters — the ONLY files importing app.integrations
├── interactions/      # transport handlers: slack.py, http.py (dir per platform if it grows)
└── locales/           # EN/FR catalogues (see i18n.md)
```

A complex feature holds subdomains (`access/{catalog,request,sync}/`), each shaped like the above, plus a `common/` shared kernel that is not itself a plugin. Names outside this table need a one-line justification in the PR; the table grows by amending this record.

### Handler discipline

A handler (any platform) does five things and nothing else: receive the platform input → translate to typed values → call **one** service method → receive `OperationResult` → render via the platform's shared renderer. Handlers are `async def`. Prohibited in handlers: business logic, vendor SDK calls, state, try/except around business outcomes (services return results; unexpected exceptions propagate to the central handler, which owns their logging). The one permitted try/except is the transport's shared helper around platform sends (`say`/`respond`), per [transport-slack.md](transport-slack.md). A handler pushing past ~30 lines is a smell that logic is leaking out of `service.py`.

### Dependency rules

- Services depend on Protocols (constructor-injected via `providers.py`); domain code depends on nothing outside the feature and the stdlib.
- Features never import other features. Cross-feature reactions go through domain events ([events.md](events.md)); shared needs get promoted to infrastructure on the second consumer ([layers.md](layers.md)).
- `app/integrations/` imports appear only under `adapters/`. Platform helpers (parser, renderer, models) come from the transport service, not the platform SDK.

## Consequences

- A new contributor can copy `geolocate/` as a template and be productive in an afternoon — that is this record's success criterion.
- Reconciling with shipped code means the standard is enforceable from today rather than aspirational; known deviations (direct `integrations.slack` imports in two interaction files, sync handlers) are small fix-PRs, not rewrites.

## Checks

- Feature independence and adapters-only import rules verified in review; mechanically enforced once [toolchain.md](toolchain.md)'s import-linter lands.
- New feature PRs match the layout table (review).
- Handler tests stub the service and assert rendering; service tests use Protocol fakes.
