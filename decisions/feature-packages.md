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

Names outside this table need a one-line justification in the PR; the table grows by amending this record. A complex feature holds subdomains, each shaped like the table above — see the next section.

### Complex features: an umbrella directory, never a flat prefix

A feature too large for one `service.py` becomes an umbrella: one directory per bounded context, one subdirectory per subdomain, plus `common/`. `access/{catalog,request,sync}` + `access/common` is the shipped instance.

```text
app/packages/<feature>/
├── __init__.py      # EMPTY — namespace only: no hookimpls, no re-exports, no entry-point line
├── common/          # shared kernel: domain vocabulary + the settings tree, no I/O
└── <subdomain>/     # shaped like the layout table above; each is a plugin
```

Three rules keep the umbrella from becoming a god package:

1. **The umbrella holds no code.** The plugin unit stays the subdomain, so registration granularity, feature-flag blast radius, and strangler increments are identical to a flat layout — [plugins.md](plugins.md) already permits subdomain plugins, and `packages/access/__init__.py` is already empty.
2. **`common/` admits only types and values with two or more subdomain consumers and no I/O.** The moment an item there calls a backing service it is either a subdomain service or an infrastructure promotion candidate ([layers.md](layers.md)). `common/` is the staging area that makes promotion visible, not the thing that prevents it.
3. **Entry-point names carry the dotted prefix**: `"incident.draft" = "packages.incident.draft"`, never `"draft"`. Entry-point names form a flat registry per group, so the bare last path component collides the day a second feature grows a `summary`. Django hits the identical wall — `AppConfig.label` defaults to the last component of the dotted path and must be unique project-wide.

**Flat `<feature>_<subfeature>` naming is rejected.** It is the convention for *separately distributed* components: the Python modular-monolith reference implementations go flat precisely because each component is its own installable distribution and the dependency resolver enforces the graph. We ship one wheel from one `pyproject.toml`, so flat naming costs without enforcing. Concretely it (a) declares subdomains to be separate features, which makes shared feature vocabulary illegal under "features never import other features" and forces either duplication or premature promotion of domain types into infrastructure, and (b) cannot be expressed as an import-linter `containers` contract, so the sibling-independence and exhaustiveness guards in Checks are unavailable. Nesting stops at two levels — `packages/<feature>/<subdomain>/`, no deeper.

### Handler discipline

A handler (any platform) does five things and nothing else: receive the platform input → translate to typed values → call **one** service method → receive `OperationResult` → render via the platform's shared renderer. Handlers are `async def`. Prohibited in handlers: business logic, vendor SDK calls, state, try/except around business outcomes (services return results; unexpected exceptions propagate to the central handler, which owns their logging). The one permitted try/except is the transport's shared helper around platform sends (`say`/`respond`), per [transport-slack.md](transport-slack.md). A handler pushing past ~30 lines is a smell that logic is leaking out of `service.py`.

### Dependency rules

- Services depend on Protocols (constructor-injected via `providers.py`); domain code depends on nothing outside the feature and the stdlib.
- Features never import other features. Cross-feature reactions go through domain events ([events.md](events.md)); shared needs get promoted to infrastructure on the second consumer ([layers.md](layers.md)). Worked example: the approval-workflow engine inside `access/request` graduates to `infrastructure/approvals/` now that SaaS-subscription and AI-key approvals need it ([approvals.md](approvals.md)); the access-specific policy and IDP/sync effect stay in the package as injected strategies.
- `app/integrations/` imports appear only under `adapters/`. Platform helpers (parser, renderer, models) come from the transport service, not the platform SDK.

## Consequences

- A new contributor can copy `geolocate/` as a template and be productive in an afternoon — that is this record's success criterion. For a complex feature the template is `access/`.
- Reconciling with shipped code means the standard is enforceable from today rather than aspirational; known deviations (direct `integrations.slack` imports in two interaction files, sync handlers) are small fix-PRs, not rewrites.
- Cost, accepted: the umbrella rule makes `packages/incident_draft` and `packages/incident_summary` deviations that must be relocated under `packages/incident/`. That is an import-path and entry-point-name change with no runtime surface change, owned by TASK-38.

## Checks

- Feature independence and adapters-only import rules verified in review; mechanically enforced once [toolchain.md](toolchain.md)'s import-linter lands.
- New feature PRs match the layout table (review).
- Handler tests stub the service and assert rendering; service tests use Protocol fakes.
- Umbrella `__init__.py` files are empty and have no entry-point line; every subdomain entry-point name is `<feature>.<subdomain>` (grep + review).
- Each umbrella carries an import-linter `layers` contract with `containers = ["packages.<feature>"]`, subdomains as pipe-separated independent siblings above `common`, and `exhaustive = true` so an undeclared subdirectory fails CI (owned by TASK-18; until it lands, review).

**Change note (2026-09-03, post-acceptance):** added the umbrella rule for complex features, resolving the shape/naming question [migration.md](migration.md) rule 5 had left open. Grounded in the shipped `access/` layout, [plugins.md](plugins.md)'s subdomain-plugin allowance, and import-linter's `containers`/`exhaustive` support, which makes the umbrella mechanically checkable and the flat alternative not.
