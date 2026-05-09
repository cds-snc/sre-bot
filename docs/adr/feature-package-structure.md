---
title: "Feature Package Structure"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture, plugins]
constrained_by: [layered-architecture.md, import-governance.md, dependency-injection.md, configuration-ownership.md, type-boundaries.md, application-lifecycle.md, plugin-registration-discovery.md, multi-transport-architecture.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Feature Package Structure

## Context and Problem Statement

The application's domain layer lives at `app/packages/`. Each subdirectory is a feature — a vertical slice that owns the routes, services, value types, and (where needed) outbound adapters that deliver one cohesive piece of the product. The number of features grows as the product grows; the cost of deciding where a new file goes, and the risk of two features accidentally coupling to each other, both compound with that growth.

The problem this record addresses: **what is the canonical internal layout of a feature package — required submodules, optional submodules, public surface, and rules for cross-subdomain composition inside a single feature — that every feature follows so the corpus stays uniform as it scales?** The answer determines:

1. Where a contributor places a new file when adding behaviour to a feature, with no need to consult prior art for every decision.
2. Which submodules are visible across the rest of the application (the public surface) versus which are private implementation detail.
3. How a feature that grows beyond a single cohesive purpose splits into subdomains without breaking the per-feature isolation guarantee.
4. Where feature-owned outbound adapters live so they remain the only feature-side files permitted to import vendor clients (the existing import contract delegates the rule but does not specify the location).

**Constraints:**

- The corpus has accepted three position layers (`app/clients/`, `app/infrastructure/`, `app/packages/`) with strict downward dependency flow. Feature packages live in the topmost layer and consume infrastructure through Protocols, never via concrete vendor types.
- Feature packages are independent: no feature imports from another feature; cross-feature coordination goes through shared infrastructure or domain events.
- Per-feature configuration is owned by the feature (its own `BaseSettings` subclass); cross-feature configuration is not introduced.
- Feature settings and feature-local composition obey the no-module-level-boot-work rule: provider functions and `BaseSettings()` constructors are invoked from inside functions called by the lifespan or by request handlers.
- The public surface is `__init__.py`'s `__all__`. Wildcard imports are not used.

**Non-goals:**

- This record does not pick the plugin discovery or registration mechanism (entry points, Pluggy hookspecs, hookimpl signatures). It specifies *where* hookimpls live; the registration framework decision is separate.
- This record does not define the multi-transport dispatch protocol — how an inbound HTTP request, Slack event, or Teams payload is routed to a feature's transport entry point. It specifies *where* transport entry points live; the dispatch decision is separate.
- This record does not define HTTP API conventions, error mapping, or validation rules. It specifies that a feature's HTTP routes live at a known location; the API conventions are separate.
- This record does not define test layout, fixtures, or coverage standards.
- This record does not define the background-execution placement (long-running tasks, scheduled jobs).
- This record does not redefine the `app/packages/<feature>/adapters/` rule — that the adapter is the only feature-side file permitted to import from `app/clients/` is already established by the import contract. This record specifies the directory's location and naming.

## Considered Options

**Option 1 — Free-form layout.** No prescribed internal structure. Each feature decides for itself; reviewers verify against general "vertical slice" principles. Names and locations vary across features.

**Option 2 — Strict required-submodule layout.** Every feature has a fixed file set (`__init__.py`, `service.py`, `routes.py`, `domain.py`, `models.py`, `settings.py`, `providers.py`, `adapters/`), even when a given feature does not need a submodule. Empty placeholder files exist for the unused ones.

**Option 3 — Conventional layout: small required core, larger optional set, names fixed.** A short list of required files defines the minimum feature; a longer list of optional files defines the conventional names a feature uses *if* it has the corresponding concern. No empty placeholders. The set of names and their meanings is fixed across the codebase.

**Option 4 — Conventional layout with simple-vs-complex bifurcation.** As Option 3, but with explicit handling of multi-subdomain features. A feature that is one cohesive purpose uses the *simple* layout; a feature that contains multiple cohesive subdomains (each with its own services, routes, and possibly settings) uses the *complex* layout, in which subdomains live as nested packages and a `common/` sibling holds the intra-feature shared kernel.

## Decision Outcome

**Chosen: Option 4 — conventional simple/complex layouts with fixed submodule names.**

Most features are a single cohesive purpose and are best served by the simple, flat layout. A small number of features grow into multiple subdomains over time; bolting subdomain organization on after the fact (or splitting the feature into two) is more expensive than recognizing that complex features need an explicit, codified shape from the moment they pass the simple-vs-complex threshold. Both layouts use the same set of submodule names so that a reader who knows the simple layout can navigate a complex feature with no relearning.

### Submodule directory: a single feature

A simple feature is a single cohesive purpose. Its layout is flat under `app/packages/<feature>/`:

```text
app/packages/<feature>/
  __init__.py          # required: public surface; hookimpls; __all__
  service.py           # required: feature business logic
  models.py            # optional: pydantic request/response schemas (HTTP boundary)
  domain.py            # optional: frozen dataclasses, Enums, Literals (internal value types)
  routes.py            # optional: FastAPI routes; HTTP-only features
  slack/               # optional: Slack handlers, organized by Slack's native method categories
    __init__.py
    commands.py        # slash command handlers
    events.py          # Slack event handlers
    actions.py         # message-action / block-action handlers
    shortcuts.py       # global / message shortcut handlers
    views.py           # view submission / closure handlers
  teams/               # optional: Teams handlers, organized by Teams' native method categories
    __init__.py
    messages.py        # text / attachment messages
    card_actions.py    # Adaptive Card Action.Submit handlers
    invokes.py         # task-module fetch/submit, message-extension queries, etc.
  adapters/            # optional: feature-owned outbound adapters
    __init__.py
    <provider>.py
  providers.py         # optional: feature-local DI/composition (lru_cache wrappers, per-feature wiring)
  settings.py          # optional: feature BaseSettings subclass
```

**Required.** `__init__.py` and `service.py` are the irreducible minimum. `__init__.py` declares the public surface; `service.py` holds the feature's business logic.

**Optional.** Other submodules exist only when the feature has the corresponding concern. A feature with no HTTP transport has no `routes.py`. A feature with no Slack handlers has no `slack/` directory; same for `teams/` and any other platform. A feature with no outbound integration has no `adapters/`. A feature with no per-feature configuration has no `settings.py`.

**Per-platform layout.** Each platform the feature handles gets its own subdirectory whose internal files mirror that platform's native method categorization. Slack's categories (commands, events, actions, shortcuts, views) become files under `slack/`; Teams' categories (messages, card actions, invokes) become files under `teams/`. The categorization is owned by the platform's own ADR (`transport-slack.md`, `transport-teams.md`); this record names the *location* where those files live. There is no `interactions/` umbrella directory — the previously proposed unified-transport abstraction was rejected because platforms are heterogeneous and a single file per platform is too coarse once each platform has multiple native categories.

**Naming is fixed.** A feature does not use alternative names (`controllers.py`, `handlers.py`, `repository.py`, `clients.py`) for the same concept. The fixed names are how the codebase scales — every feature reads the same way.

### Submodule directory: a complex (multi-subdomain) feature

A complex feature is one whose internal structure cleanly partitions into multiple subdomains, each with its own services, transport entry points, and possibly settings. The layout adds one level of nesting and a sibling `common/` for the intra-feature shared kernel:

```text
app/packages/<feature>/
  __init__.py          # required: umbrella registration; sole hookimpl entry
  common/              # required for complex features: intra-feature shared kernel
    __init__.py        # marker; may re-export shared types via __all__
    events.py          # domain events for cross-subdomain communication
    settings.py        # feature-wide settings (if shared across subdomains)
    providers.py       # intra-feature shared composition (singletons consumed by subdomains)
    domain.py          # shared value types and Protocols (consumed by subdomains)
  <subdomain>/
    __init__.py        # empty package marker; no hookimpls here
    service.py
    domain.py          # subdomain-private types
    routes.py          # optional: subdomain HTTP routes
    slack/             # optional: subdomain-local Slack handlers (commands.py, events.py, …)
    teams/             # optional: subdomain-local Teams handlers (messages.py, card_actions.py, …)
    adapters/          # subdomain-local outbound adapters
    providers.py       # subdomain-local composition
    settings.py        # optional subdomain-specific settings
```

**Umbrella-only registration.** The feature's `__init__.py` is the **sole** hookimpl entry for the entire feature. Subdomain `__init__.py` files are empty package markers. The umbrella's hookimpls compose subdomain routers (calling each subdomain's transport entry point) and gate registration on feature-level settings before any router is included into the FastAPI app. This keeps Pluggy registration uniform across simple and complex features (one hookimpl set per feature) and ensures settings-based gating happens once, at the umbrella, rather than scattered across subdomain registrations.

**No umbrella `providers.py`.** Intra-feature shared composition lives at `common/providers.py`. Subdomain-local composition lives at `<subdomain>/providers.py`. There is no separate umbrella `providers.py`, because the umbrella's only job is registration, not composition.

**Cross-subdomain communication is constrained to three channels:**

1. **Domain events** defined in `common/events.py`, dispatched through shared infrastructure (the application's event bus).
2. **Shared value types and Protocols** imported from `common/`. Subdomains depend on `common/` only; `common/` does not depend on any subdomain.
3. **Shared infrastructure services** consumed by both subdomains independently (each subdomain's `providers.py` resolves the infrastructure service).

Direct subdomain-to-subdomain imports are forbidden. The intra-feature import contract mirrors the inter-feature independence rule: each subdomain is an isolated vertical slice within the feature.

### Public surface (`__init__.py` rules)

The `__init__.py` of a feature declares its public surface explicitly. The rules:

- **`__all__` is required.** Every name a consumer can import from the feature appears in `__all__`. Names not listed are private.
- **What appears in `__all__`.** Hookimpl functions (so the plugin framework discovers them at registration). Public types if and only if a consumer outside the feature legitimately depends on them — typically only the router or schema types referenced by another feature's adapter going through shared infrastructure, which is rare.
- **What does not appear.** Internal services, repositories, domain dataclasses, adapter implementation classes, and `BaseSettings` subclasses. These are private to the feature.
- **No wildcard imports.** Neither `from <feature> import *` in consumers nor `from .module import *` inside the feature.
- **No side-effecting imports.** `__init__.py` does not call provider functions, instantiate `BaseSettings`, configure logging, or mutate global state.

A subdomain's `__init__.py` (in a complex feature) is an empty package marker (no `__all__` declaration, no re-exports, no hookimpls). The umbrella `__init__.py` is the only place hookimpls are declared for that feature.

### Transport entry points

The placement of inbound handler code follows the platform model: each platform gets its own subdirectory under the feature, with internal files mirroring that platform's native method categories. HTTP is the exception — its single category (route handlers) lives in a top-level `routes.py`.

| Platform | Location | Internal organization |
| --- | --- | --- |
| HTTP | `routes.py` | A single `APIRouter` and its route functions. Mounted by the feature's `register_routes` hookimpl. |
| Slack | `slack/` | One file per native Slack category: `commands.py`, `events.py`, `actions.py`, `shortcuts.py`, `views.py`. Each platform-specific hookimpl in `__init__.py` (e.g., `register_slack_command`) imports from the relevant file. |
| Teams | `teams/` | One file per native Teams category: `messages.py`, `card_actions.py`, `invokes.py`, `installation_update.py`. Same pattern. |
| Other platforms | `<platform>/` | Same pattern: one subdirectory per platform, internal files mirror the platform's native method categorization, owned by that platform's ADR. |

A feature that handles HTTP and Slack has both `routes.py` and `slack/`. A feature that handles only Slack has only `slack/` — there is no requirement to create empty parallel directories.

Handler files are the boundary between platform-specific shape (a FastAPI `Request`, a Slack payload, a Teams card-action body) and the feature's `service.py`. They map inbound shapes to service-method arguments and service-method return values to platform-specific outbound shapes. Business logic does not live in handler files.

The internal categorization of any platform's subdirectory (e.g., the choice to split Slack handlers into `commands.py` / `events.py` / `actions.py`) follows that platform's native model and is owned by the platform's own ADR. This record specifies that *each platform has its own subdirectory*; the catalogue of files inside is platform-shaped.

### Feature-owned outbound adapters

Some features integrate with an external system that no other feature uses. The adapter (Protocol + concrete implementation) for that integration lives inside the feature, not in `app/infrastructure/`:

- **Location.** `app/packages/<feature>/adapters/<provider>.py` for simple features. `app/packages/<feature>/<subdomain>/adapters/<provider>.py` for subdomain-local adapters in complex features. (A complex feature may also place a feature-shared adapter under `common/adapters/<provider>.py` if multiple subdomains use the same external system.)
- **Shape.** Each adapter file exposes a `typing.Protocol` describing the operation the feature needs and a concrete implementation that wraps a vendor client from `app/clients/`. The Protocol is the only thing the feature's `service.py` imports; the concrete implementation is wired via the feature's `providers.py`.
- **Vendor-import rule.** The adapter file is the only feature-side file permitted to import from `app/clients/`. This is enforced by the import contract; the location rule in this record makes that contract trivially satisfiable.
- **Promotion to infrastructure.** When a second feature needs the same external system, the Protocol and implementation are promoted to `app/infrastructure/<service>/` and become a shared infrastructure service. The first feature switches its service to consume the infrastructure Protocol; the feature-local adapter file is deleted. The trigger is the second consumer, not a count, a pattern, or a guess at future need.

### Feature-local settings

A feature with per-feature configuration declares a `BaseSettings` subclass in `settings.py` and exposes a `@lru_cache(maxsize=1)`-wrapped provider function. The settings class is private to the feature — no other feature imports it, and no `AppSettings`-style aggregator pulls feature settings into a global object. Cross-feature configuration does not exist by construction.

For a complex feature, settings shared across subdomains live in `common/settings.py`; subdomain-specific settings live in `<subdomain>/settings.py`. Subdomain settings are private to the subdomain and consumed via the subdomain's own provider function.

### Feature-local composition (`providers.py`)

A feature with internal composition (lru-cached singletons, internal wiring of services to adapters) declares the providers in `providers.py`. The rules:

- The provider function returns a Protocol type, never a concrete class. (The concrete class is an implementation detail behind the provider.)
- The provider function calls into infrastructure providers (`from app.infrastructure.<service> import get_<service>`) when the feature's service depends on infrastructure. It does not import infrastructure concrete-implementation files directly.
- The provider function may call into the feature's own `adapters/<provider>.py` to instantiate a feature-owned adapter, passing in vendor clients obtained from `app/clients/` provider functions.
- No top-level call to a provider function exists in `providers.py` itself; provider functions execute when the lifespan or a request handler invokes them.

A feature with no internal composition (its service holds no dependencies that need wiring beyond an injected infrastructure Protocol) has no `providers.py`. Direct `Annotated[Protocol, Depends(get_<service>)]` injection on the route handler is sufficient and idiomatic.

### Where each ADR-recognized type lives

| Type purpose | File |
| --- | --- |
| HTTP request / response schema | `models.py` |
| Internal value type / dataclass | `domain.py` (or `<subdomain>/domain.py`, or `common/domain.py`) |
| Service-layer Protocol consumed by route handlers | declared inside `service.py` (or imported from `common/` for complex features) |
| Outbound integration Protocol (feature-owned) | `adapters/<provider>.py` |
| `BaseSettings` subclass | `settings.py` (or `common/settings.py`) |
| Domain event (cross-subdomain) | `common/events.py` |

This table is a flattening of the `type-boundaries` decision into the layout: each type construct has a known home in the feature package.

## Consequences

**Positive:**

- A new contributor can navigate any feature by reading one layout and one set of name conventions; the cost of context-switching between features is bounded.
- A feature that grows from simple to complex has a documented migration path: introduce `common/`, move shared types and events into it, add subdomain directories, and lift hookimpls to the umbrella. The change is mechanical and produces a single reviewable PR.
- The umbrella-only registration rule keeps Pluggy registration uniform — the framework discovers hookimpls at one location per feature, regardless of how many subdomains the feature contains.
- Feature-owned outbound adapters have a fixed location, which makes the import contract trivially enforceable: the only feature-side file allowed to import from `app/clients/` is `adapters/<provider>.py`.
- The simple/complex distinction stops the "what if we add another piece later" anxiety that would otherwise push every feature toward over-structured layouts. A simple feature is allowed to be simple.

**Tradeoffs accepted:**

- The complex-feature layout adds one nesting level over the simple form. The cost is one more directory hop when reading a multi-subdomain feature's code; the benefit is that subdomain isolation is enforced by the structure itself.
- The fixed-naming rule prohibits `controllers.py`, `handlers.py`, `repository.py`, and similar alternative names that may feel natural to contributors arriving from other codebases. The cost is an unfamiliar vocabulary on day one; the benefit is uniform vocabulary across every feature.
- A feature that legitimately spans two subdomains but is very small still pays the complex-layout cost (the `common/` directory, the empty subdomain `__init__.py` markers). The cost is small; alternatively, the feature can stay flat and split only when the second subdomain is non-trivial.

**Risks:**

- A feature drifts from the layout (a service-like file under a different name, hookimpls scattered across subdomain `__init__.py` files in a complex feature, an outbound adapter outside `adapters/`). Mitigation: the layout is enforced by code review against this record's rules; the import contract catches the most-damaging deviations (vendor imports outside `adapters/`, cross-feature imports) automatically.
- A simple feature is prematurely promoted to the complex layout because its author anticipates future subdomains. Mitigation: the migration from simple to complex is mechanical and one-time; the rule is "simple by default, complex when a second subdomain materially exists."
- The `common/` shared kernel grows into a god-package as a complex feature evolves, accumulating utilities that should belong in a single subdomain or in shared infrastructure. Mitigation: the rule that `common/` contains *cross-subdomain* shared types only is a code-review check; types used by exactly one subdomain belong in that subdomain, not in `common/`.

## Confirmation

Compliance is verified by:

- **Repository contents.** Every directory under `app/packages/` is a feature with `__init__.py` and `service.py`. Every multi-subdomain feature has `common/` and at least two subdomain directories with empty `__init__.py` files. Every feature with a feature-owned outbound integration has `adapters/<provider>.py`.
- **Public surface.** Every feature `__init__.py` declares `__all__`; no `__init__.py` performs side effects (no provider calls, no `BaseSettings()` construction, no logging configuration). Subdomain `__init__.py` files are empty package markers in complex features.
- **Import contract.** The accepted import-graph contracts already encode the layered and per-feature isolation rules (cross-feature, vendor purity, feature-vendor boundary). No additional contract is needed; the layout in this record makes the existing contracts enforceable.
- **Code review.** A PR that introduces a new feature is reviewed against the layout (required submodules present, fixed names used, no alternative names, public surface declared in `__all__`). A PR that promotes a simple feature to complex is reviewed against the migration shape (umbrella-only registration, `common/` populated with truly cross-subdomain content, subdomain `__init__.py` files emptied of hookimpls).

## Source References

1. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the vertical-slice principle the layout encodes: a feature is organized around its end-to-end purpose (from transport to data), not by horizontal technical layer; cross-slice coupling is minimized in favour of slice-internal cohesion. Grounds both the simple flat layout and the complex per-subdomain layout (each subdomain is itself a vertical slice).

2. Modular Monolith Primer — Kamil Grzybek
   - URL: <https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer>
   - Accessed: 2026-05-08
   - Relevance: Establishes that a module in a modular monolith is defined by independence (loose coupling), self-containment (organized around a business domain rather than a technical layer), and encapsulation (everything hidden behind a defined interface). Grounds the per-feature isolation and explicit-public-surface (`__all__`) rules.

3. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that a feature's outbound integrations are adapters at the application boundary, exposing ports (Protocols in this codebase) to internal code. Grounds the rule that feature-owned adapters live in `adapters/<provider>.py` as the boundary between the feature's service-layer contract and a vendor client.

4. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that wiring happens at known composition points — for this codebase, the application's lifespan, infrastructure providers, and feature-local `providers.py` files. Grounds the rule that `providers.py` is the feature's local composition surface and that route handlers receive Protocols by injection rather than constructing implementations themselves.

5. Architecture Patterns with Python (Cosmic Python), Chapter 9 — Bob Gregory and Harry Percival
   - URL: <https://www.cosmicpython.com/book/chapter_09_all_messagebus.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes domain events as dataclasses defined inside the domain layer, dispatched through a message bus that decouples handlers from each other. Grounds the rule that cross-subdomain communication in a complex feature uses domain events from `common/events.py`, not direct subdomain-to-subdomain imports.

6. PEP 8 — Imports
   - URL: <https://peps.python.org/pep-0008/#imports>
   - Accessed: 2026-04-29
   - Relevance: Establishes that imports are explicit and that wildcard imports (`from x import *`) are discouraged. Grounds the rule that `__init__.py` re-exports are explicit (`__all__`) rather than wildcard, and that side-effecting imports are avoided.

## Change Log

- 2026-05-08: Created. Establishes two canonical feature-package layouts: simple (flat) and complex (multi-subdomain with `common/` shared kernel). Names submodule files (`__init__.py`, `service.py`, `models.py`, `domain.py`, `routes.py`, `interactions/`, `adapters/`, `providers.py`, `settings.py`) and pins their meanings; alternative names (`controllers.py`, `handlers.py`, `repository.py`) are not used. Establishes umbrella-only hookimpl registration for complex features, with subdomain `__init__.py` files as empty package markers. Establishes that cross-subdomain communication in a complex feature uses one of three channels (domain events from `common/events.py`, shared types from `common/`, shared infrastructure services). Pins the location of feature-owned outbound adapters at `adapters/<provider>.py` (or `<subdomain>/adapters/<provider>.py` for complex features), making the existing vendor-import contract trivially enforceable. Removes `plugin-registration-discovery.md` from `constrained_by` (the relationship is reversed: plugin registration consumes the layout this record defines).
- 2026-05-08: Replaced the `interactions/<transport>.py` umbrella with **per-platform directories**. Each platform a feature handles gets its own subdirectory (`slack/`, `teams/`, `<platform>/`) whose internal files mirror that platform's native method categories (Slack: `commands.py` / `events.py` / `actions.py` / `shortcuts.py` / `views.py`; Teams: `messages.py` / `card_actions.py` / `invokes.py`). HTTP retains its single `routes.py` short form. Reason: the corpus rejected the unified-platform abstraction the `interactions/<transport>.py` rule implied — platforms are heterogeneous and a single file per platform is too coarse once each platform has multiple native categories. The categorization inside any platform's subdirectory is owned by that platform's own ADR (`transport-slack.md`, `transport-teams.md`); this record names only the directory's location and that its contents follow the platform's native model. Added `plugin-registration-discovery.md` and `multi-transport-architecture.md` to `constrained_by` to reflect the now-accepted records this layout depends on. Subdomain layouts in complex features follow the same per-platform-directory rule.
