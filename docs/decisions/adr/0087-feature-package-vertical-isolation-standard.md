---
adr_id: ADR-0087
title: "Feature Package Vertical Isolation Standard"
status: Draft
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Package and Plugin Architecture
secondary_domains:
  - Dependency and Composition
  - Testing and Quality Gates
owners:
  - SRE Team
date_created: 2026-05-06
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-02
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
  - ADR-0078
impacts:
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0062
  - ADR-0065
  - ADR-0077
  - ADR-0078
  - ADR-0085
  - ADR-0086
  - ADR-0088
related_packages:
  - app/packages/access
  - app/packages/geolocate
---

# Feature Package Vertical Isolation Standard

## Context

- Problem statement: There is no ADR that defines what "vertically isolated" means for a
  feature package in `app/packages/`. ADR-0048 establishes the Application → Service →
  Infrastructure flow and names `app/packages/` as the canonical home for business
  logic. ADR-0059 governs how a feature package interacts with output platforms (Slack,
  Teams). Neither record defines the *internal* structure of a feature package, what a
  package may contain, what it may import from sibling packages, or how its test scope
  is bounded.

  The result is that `app/packages/` has accumulated conventions that are internally
  consistent within each package but were never formally ratified. No rule prevents a
  future package from importing from a sibling package's internal modules, no rule
  defines whether a sub-package (e.g., `access/request`) counts as the same vertical as
  its parent (`access/`) or as an independent vertical, and no rule determines whether
  package-specific tests should be colocated with the package or aggregated in the
  top-level `app/tests/` tree.

  **The current package landscape:**

  | Package | Sub-packages | Hookimpl entry point | HTTP routes | Platform handlers |
  |---------|-------------|----------------------|-------------|-------------------|
  | `access` | `request`, `sync`, `catalog`, `common` | `access/request/__init__.py`, `access/sync/__init__.py`, `access/catalog/__init__.py` | Yes — per sub-package | Slack (sync, request, catalog) |
  | `geolocate` | none | `geolocate/__init__.py` | Yes | Slack, Teams (stub), Discord |

  **The sub-package boundary question:**

  The `access` package is split into three registerable sub-packages (`request`, `sync`,
  `catalog`) each with its own `__init__.py` bearing `@hookimpl` functions and its own
  `providers.py`. They share a `common/` sub-package for settings, events, and runtime
  config. This structure exists in the codebase but its governing rules are not
  documented:

  - Is `access/request` a fully independent vertical (no shared state with `access/sync`
    except via infrastructure services)?
  - Is `access/common/` a legitimate internal shared library, or is it a code smell that
    signals the three sub-packages are actually one vertical?
  - Should `access/sync` be allowed to import from `access/request` (e.g., to react to
    a request-approved event)?

  Currently, `access/sync/__init__.py` imports from `packages.access.common.events`:

  ```python
  from packages.access.common.events import REQUEST_APPROVED
  ```

  And `access/sync/providers.py` imports from `packages.access.common.providers`:

  ```python
  from packages.access.common.providers import get_access_runtime_config
  ```

  These cross-sub-package imports within the same top-level package are currently
  unregulated.

  **What features currently import from infrastructure (coupling evidence):**

  ```python
  # access/sync/__init__.py
  from infrastructure.services import get_event_dispatcher, hookimpl

  # access/sync/interactions/slack.py
  from infrastructure.services import get_idempotency_service, t

  # geolocate/__init__.py
  from infrastructure.services import hookimpl

  # geolocate/service.py
  from infrastructure.services import get_maxmind_client   # import of concrete provider
  ```

  The direct import of provider functions (`get_event_dispatcher`, `get_idempotency_service`,
  `get_maxmind_client`) couples feature packages to `infrastructure.services` as the
  import address. This coupling is the consumer-side symptom that ADR-0085 (barrel
  dissolution) and ADR-0086 (consumption boundary) address structurally and
  mechanically. ADR-0087 addresses the *package design* question: what does a
  well-isolated feature package look like, and what must its boundary rules be,
  independently of the resolution chosen for ADR-0085 and ADR-0086?

  **The cross-package import gap:**

  There is no rule today that explicitly prohibits `packages/geolocate/` from importing
  `packages/access/domain.py`. ADR-0048 Boundary 1 prohibits packages from importing
  from `app/modules/`, but it does not address peer-to-peer package imports. This gap
  becomes important as the `packages/` tree grows: if packages may freely import from
  each other, vertical isolation is only nominal.

  **The test isolation gap:**

  All current tests live under `app/tests/`, mirroring the package path:

  ```
  app/tests/unit/packages/access/request/test_policies.py
  app/tests/integration/packages/access/request/test_routes.py
  app/tests/integration/packages/access/sync/adapters/aws/conftest.py
  ```

  This structure is governed by ADR-0062. Whether tests should be colocated with the
  package they test (inside `app/packages/access/tests/`) or remain in the top-level
  tree is not governed. Colocation would increase vertical isolation (a package ships
  with its own tests); top-level aggregation makes CI fixture sharing easier but
  reduces package portability.

  **Package route registration — pluggy as the registration mechanism:**

  Packages register their FastAPI routes by implementing the `register_routes(app)`
  hookspec:

  ```python
  @hookimpl
  def register_routes(app):
      app.include_router(geolocate_router)
  ```

  This is the *only* governed mechanism for route registration (ADR-0049). But the
  hookspec is defined in `infrastructure/hookspecs/features.py`, and calling it requires
  the pluggy plugin manager to discover and call every registered hookimpl. There is no
  rule that defines the router prefix structure, tag strategy, or whether each package
  may define more than one router.

  **What "vertically isolated" means informally vs. formally:**

  The user intent is that each feature package should be able to grow, be tested, be
  refactored, and eventually be extracted without coupling to the internal implementation
  of any sibling package. This is the "vertical slice" pattern, where each slice owns:
  its domain model, its service layer, its HTTP route handlers, its platform handlers,
  its settings, and its tests. Infrastructure services are shared horizontally across
  all slices but consumed through a stable Protocol contract, not through direct
  implementation imports.

  The gap is that this intent has never been made formal, has no stated boundary rules,
  and has no enforcement mechanism. The `packages/` directory contains patterns that
  reflect the intent, but the intent itself is not an ADR.

  **Relationship to ADR-0085, ADR-0086, ADR-0088:**

  ADR-0085 governs what the infrastructure barrel exports (structural).
  ADR-0086 governs how features call infrastructure at each call context (mechanical).
  ADR-0088 governs how features support multiple input transports (interaction dispatch).
  This ADR governs what a feature package *is*: its canonical structure, its permitted
  imports, its cross-package isolation rules, and its test scope boundary. The four
  ADRs are complementary; none is a prerequisite for the others.

- Business/operational drivers:
  - Provide an explicit, enforceable definition of "vertically isolated feature package"
    so that new packages are created with consistent structure and known boundaries.
  - Prevent peer-to-peer coupling between packages as the `packages/` tree grows.
  - Clarify the sub-package question: when is it correct to split a feature into
    sub-packages (e.g., `access/request` + `access/sync`) vs. keeping it as a single
    package, and what may sub-packages within the same top-level package share?
  - Establish the test isolation model: colocated tests vs. aggregated top-level tree.
  - Give infrastructure teams and feature teams a shared vocabulary for "what a package
    boundary means" so that code review has clear criteria.

- Constraints:
  - ADR-0045 P3: business logic belongs in `app/packages/<domain>`. The isolation model
    must not make placing business logic in packages impractical.
  - ADR-0048 B1: packages must not import from `app/modules/`. The new ADR extends,
    not relaxes, this boundary.
  - ADR-0049: plugin registration via pluggy hookspecs is the governed mechanism.
    The isolation model must be compatible with the discovery and invocation model
    defined in ADR-0049 (all hookimpls discovered at startup, called by the plugin
    manager, not by direct package import).
  - ADR-0059: feature interaction boundaries (how features interact with output platforms
    via `interactions/` sub-modules) must remain compatible with the isolation model.
  - ADR-0062: the current test layout (`app/tests/unit/packages/...`,
    `app/tests/integration/packages/...`) is governed. Any change to test colocation
    must amend or supersede ADR-0062.
  - ADR-0065: domain data inside packages must use `@dataclass(frozen=True)`. The
    isolation model must preserve this type boundary rule.
  - Infrastructure services are shared across all packages — they are not owned by any
    one vertical. The isolation model governs how packages *consume* them (via ADR-0086),
    not whether they exist.

- Non-goals:
  - This record does not define the call-site mechanics for consuming infrastructure
    services (governed by ADR-0086).
  - This record does not define how packages support multiple input transports
    (governed by ADR-0088).
  - This record does not define the barrel structure of `infrastructure/services/`
    (governed by ADR-0085).
  - This record does not change the pluggy hookspec definitions or startup sequencing
    (governed by ADR-0049).
  - This record does not govern `app/modules/` — those are frozen legacy code.

- Research required before Decision:
  - **Intra-package shared library legitimacy (`access/common`):** Whether a top-level
    feature package is permitted to contain an internal `common/` sub-package shared
    across its sub-domains (e.g., `access/common` shared by `access/request`,
    `access/sync`, `access/catalog`) requires research into Python package structuring
    best practices and vertical slice architecture literature. The question is whether
    this constitutes a legitimate "intra-package library" (analogous to a private
    utility module within a bounded context) or whether it is a coupling smell that
    signals the sub-packages are too tightly related to be independent verticals.
    Online research into vertical slice / feature-oriented architecture patterns in
    Python projects must be completed before this question can be decided.
  - **Test colocation vs top-level aggregation:** Whether tests should be colocated
    with the package they test (`packages/access/tests/`) or aggregated in a top-level
    tree (`app/tests/unit/packages/access/`, governed by ADR-0062) requires research
    into Python project layout conventions (e.g., `src/` layout patterns, pytest
    discovery conventions, packaging standards for extractable packages) and real-world
    FastAPI project structures. The decision impacts `pytest.ini` discovery configuration,
    CI fixture sharing, and the definition of "extractable package." This research must
    precede any amendment or supersession of ADR-0062.

## Decision

*TBD — pending Context review and author approval.*

## Alternatives Considered

*TBD*

## Consequences

*TBD*

## Compliance and Boundaries

*TBD*

## Best-Practice Revalidation

*TBD*

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Context under author review. Decision not yet written.
- Follow-up actions:
  - Confirm Context with author.
  - Proceed to Decision section once Context is approved.
  - Challenge review (Round 1) after Decision section is complete.

## Source References

*TBD*

## Implementation Guidance

*TBD*

## Change Log

- 2026-05-06: Created as Draft. Addresses the gap in governance of feature package
  vertical isolation: structure, cross-package import rules, sub-package boundaries,
  and test scope. Companion to ADR-0085, ADR-0086, and ADR-0088.
