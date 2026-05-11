---
title: "Type Boundaries"
status: Accepted
type: Principle
tier: Tier-1
governance_domain: [application]
concerns: [architecture]
constrained_by: [decision-record-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Type Boundaries

## Context and Problem Statement

A modular Python application crosses several distinct boundaries where data takes different shapes and serves different purposes: HTTP request and response bodies cross a trust boundary from outside the process; environment variables carry configuration into the process at startup; vendor SDK responses cross from third-party clients into adapters; domain values move between feature packages and infrastructure services through Protocol contracts; closed sets of categorical values (statuses, modes) appear at multiple of these boundaries. Each boundary imposes different requirements on the type construct that represents the data: validation, immutability, framework-independence, structural conformance, runtime parsing, schema generation.

Python offers multiple type constructs (`typing.Protocol`, `@dataclass`, Pydantic `BaseModel`, `pydantic_settings.BaseSettings`, `typing.TypedDict`, `Enum`, `typing.Literal`, named tuples, plain classes). Each is fit-for-purpose at a specific boundary; none is the right answer everywhere. When the choice is left to local preference, the application accumulates inconsistent representations of the same concept (a `User` modelled as a Pydantic model in one module, a dataclass in another, a dict in a third), runtime overhead in places where it is not needed (Pydantic validation on internal in-process data), and bypass paths where it is needed (untyped dicts crossing the HTTP edge).

The core problem: **for each boundary the application crosses, which Python type construct represents data at that boundary, and why?** The allocation has to be principled — driven by what each boundary requires — rather than by what is locally convenient.

**Constraints:**

- The application uses Python 3.12+ on FastAPI, Pydantic v2, and `pydantic-settings`.
- All external input that crosses the application's trust boundary (HTTP, webhooks, queue messages, external API responses) must be validated before being used by domain logic.
- All configuration must be read from environment variables ([cloud-portability.md](cloud-portability.md), Contract 1).
- Service contracts between layers must be expressible as `typing.Protocol` interfaces ([cloud-portability.md](cloud-portability.md), Contract 4; [layered-architecture.md](layered-architecture.md)).
- The cross-layer return contract `OperationResult` must carry a closed status enumeration ([operation-result-pattern.md](operation-result-pattern.md)).

**Non-goals:**

- This record does not enumerate every domain type or define their fields — it allocates the *kind* of type construct, not the contents.
- This record does not govern serialization formats on the wire (JSON shape conventions, OpenAPI schema details) — see [api-design-error-mapping.md](api-design-error-mapping.md).
- This record does not define the dependency-injection mechanism that wires Protocols to implementations — see [dependency-injection.md](dependency-injection.md).
- This record does not govern where settings classes live in the source tree, how they are partitioned across domains, or how their providers are wired — see [configuration-ownership.md](configuration-ownership.md). Settings *placement and ownership* are a separate concern from the *type construct* used at the configuration boundary.

## Considered Options

**Option 1 — Allocate type constructs by boundary.** The construct is determined by *where* the data lives in the architecture, not by what shape it has. The same logical concept (e.g., a user) can have different representations at the HTTP boundary, in domain logic, and in adapter internals — each one fit-for-purpose at its boundary.

**Option 2 — Use one construct everywhere (e.g., Pydantic `BaseModel` for all data).** A single mental model. Validation is uniform.

**Option 3 — Use plain dicts everywhere; rely on documentation and discipline.** Maximally lightweight at runtime; minimal up-front structure.

## Decision Outcome

**Chosen: Option 1 — allocate type constructs by boundary.**

The choice of construct is driven by the requirement at the boundary, not by the data's shape or by developer familiarity. The same logical concept may be represented by multiple constructs at different points in the application; each representation is responsible only for the concerns of its own boundary.

### The allocation

| Boundary / role | Type construct | Why this construct |
| --- | --- | --- |
| Service contracts between layers (composed-service Protocols, feature-owned outbound-adapter Protocols, hookspecs) | `typing.Protocol` | Structural subtyping decouples consumers from implementations and enables in-process stub doubles for testing without inheritance ceremony. |
| Internal value types crossing package or service boundaries (domain models, value objects, the cross-layer return contract `OperationResult`) | `@dataclass(frozen=True)` | Immutable, framework-independent, lightweight to construct and pass. Suitable for the internals of a stateless application where shared values must not be mutated by their consumers. |
| Untrusted external input (HTTP request bodies, webhook payloads, queue message bodies, external API responses parsed at the trust boundary) | `pydantic.BaseModel` | Runtime validation, type coercion, JSON Schema generation. The boundary at which the application receives data it did not produce is the place where these are needed. |
| Untrusted external output that must be schema-described (HTTP response bodies, OpenAPI documentation) | `pydantic.BaseModel` | Same reasons in reverse: schema-described, validated serialization at the wire. |
| Environment-variable configuration (root settings) | `pydantic_settings.BaseSettings` | Typed parsing, validation, and defaulting for environment-supplied configuration at process startup, per [cloud-portability.md](cloud-portability.md) Contract 1. |
| Nested configuration sections within a `BaseSettings` root | `pydantic.BaseModel` | Structured grouping inside a `BaseSettings` root. `BaseSettings` is not nested inside another `BaseSettings`; the root owns the env-var sourcing. |
| Dict-shaped vendor SDK payloads inside an adapter (e.g., a DynamoDB item, a Google API resource, a Slack event payload) before translation to a domain type | `typing.TypedDict` | Structural typing for dict-shaped data whose key set is known. Stays inside the adapter; never crosses upward. |
| Closed sets of categorical values whose identity carries semantics (status enumerations, modes, kinds) | `enum.Enum` | Identity, comparison, and exhaustive iteration. Used for the `OperationResult` status set defined in [operation-result-pattern.md](operation-result-pattern.md). |
| Type-level constraints on string or integer values (e.g., a backend selector `"memory" \| "dynamodb"`, a tier label) | `typing.Literal` | Constrains accepted values at the type level without introducing a runtime enum class. Appropriate when the value is a configuration choice rather than a domain concept. |

### Rules implied by the allocation

- **The boundary determines the construct, not the shape of the data.** A `User` is a Pydantic model at the HTTP edge, a frozen dataclass in domain logic, and a `TypedDict` (or vendor-shaped dict) inside an adapter parsing a directory provider's response. None of these representations is the canonical one — each is canonical at its own boundary.
- **Pydantic validation is for trust boundaries.** `BaseModel` does not propagate inward. Once external input has been parsed and validated at the HTTP, webhook, or queue edge, it is converted into a domain `@dataclass(frozen=True)` (or a Protocol-typed view) before being passed to feature service code.
- **Frozen is the default for value types.** Internal value types crossing a boundary are frozen unless a specific reason makes mutability necessary, in which case the mutable type does not cross a package boundary.
- **Service code depends on Protocols, not on concrete implementations.** Protocols describe what the consumer needs in domain terms; the satisfying concrete type is constructed at composition time and injected.
- **Vendor-shaped types stay inside adapters.** `TypedDict` representations of SDK payloads do not appear in feature service or domain code. The adapter translates to a domain type before returning.

### Where each construct must NOT appear

- `BaseModel` must not appear in feature domain logic, internal service contracts, or as the type of values held by frozen dataclasses. It is a wire-boundary construct.
- `BaseSettings` must not be nested inside another `BaseSettings`. The root owns env-var sourcing; nested sections use `BaseModel`.
- `TypedDict` representing a vendor SDK shape must not appear in feature service or domain modules; it is private to the adapter.
- A mutable dataclass must not cross a package boundary. Mutability is permitted only for transient, process-local state.
- Plain `dict` is not a substitute for any of the above when the key set is known and the data crosses a boundary; choose `TypedDict`, dataclass, or `BaseModel` according to the boundary.

## Consequences

**Positive:**

- The right tool runs at each boundary: validation where it matters, immutability where it matters, framework-independence where it matters, schema generation where it matters.
- Domain logic does not pay Pydantic's validation cost on values that have already been validated at the trust boundary.
- The HTTP and external-input edges produce schema-described, validated bodies; the domain layer manipulates values that are framework-independent and safe to share.
- The choice of construct for any given piece of data is a one-question decision: "at which boundary does this data live?"

**Tradeoffs accepted:**

- The same logical concept may have two or three representations across boundaries (a Pydantic model at the wire, a frozen dataclass internally, a TypedDict in an adapter). Maintaining the conversions is the cost of the allocation.
- Developers must be familiar with multiple constructs and the rule for choosing among them.

**Risks:**

- A developer unfamiliar with the allocation may use Pydantic for internal data because it is the construct they are most comfortable with. Mitigation: code review checks `BaseModel` usage; static analysis (e.g., grep-style rules in CI) flags `BaseModel` imports inside domain or service modules.
- The translation between wire and internal representations may drift if the two are edited independently. Mitigation: each adapter or route has explicit conversion functions; tests cover the round-trip where applicable.

## Confirmation

Compliance is verified by:

- **Code review.** Each new type definition is placed in the construct appropriate to its boundary. Pydantic `BaseModel` does not appear in feature domain modules; frozen dataclass does not appear as the body of an HTTP request; `BaseSettings` does not appear outside the configuration layer.
- **Static analysis.** Type checking treats Protocols as structural; `Enum` and `Literal` types are checked for exhaustive branching at consumer sites where the boundary requires it.
- **Tests.** Wire-boundary types (Pydantic models) have tests for parsing, validation, and rejection of malformed input. Internal value types (frozen dataclasses) have tests for equality and immutability where the property is load-bearing.

## Source References

1. PEP 544 — Protocols: Structural Subtyping (Static Duck Typing)
   - URL: <https://peps.python.org/pep-0544/>
   - Accessed: 2026-04-29
   - Relevance: Defines `typing.Protocol` and structural subtyping. The Protocol is the construct used at service boundaries because the consumer depends on the structural shape, not on a concrete implementation hierarchy.

2. PEP 557 — Data Classes
   - URL: <https://peps.python.org/pep-0557/>
   - Accessed: 2026-04-29
   - Relevance: Defines `@dataclass`, including the `frozen` flag for immutable instances. Grounds the use of `@dataclass(frozen=True)` for internal value types crossing package boundaries.

3. PEP 589 — TypedDict
   - URL: <https://peps.python.org/pep-0589/>
   - Accessed: 2026-05-08
   - Relevance: Defines `typing.TypedDict` for dict-shaped data whose key set is known statically. Grounds its use inside adapters for vendor SDK payload shapes.

4. PEP 586 — Literal Types
   - URL: <https://peps.python.org/pep-0586/>
   - Accessed: 2026-05-08
   - Relevance: Defines `typing.Literal` for constraining accepted values at the type level without introducing an `Enum` class. Distinguishes the Literal-vs-Enum allocation.

5. Pydantic V2 — Why Use Pydantic
   - URL: <https://docs.pydantic.dev/latest/why/>
   - Accessed: 2026-04-29
   - Relevance: Establishes Pydantic's purpose as runtime data validation, type coercion, and schema generation at the boundaries of a Python application. Grounds the use of `BaseModel` at trust boundaries (HTTP, webhooks, external payloads) and not internally.

6. Pydantic Settings V2 — Configuration
   - URL: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
   - Accessed: 2026-04-29
   - Relevance: Establishes `pydantic_settings.BaseSettings` for environment-variable-sourced configuration with typed parsing and validation. Grounds the configuration boundary in this allocation, working with [cloud-portability.md](cloud-portability.md) Contract 1.

7. FastAPI — Dependencies
   - URL: <https://fastapi.tiangolo.com/tutorial/dependencies/>
   - Accessed: 2026-04-29
   - Relevance: Defines the framework's mechanism for injecting parsed-and-validated request models (Pydantic `BaseModel`) into route handlers, and Protocol-typed services into the same handlers via `Depends`. Confirms that the Pydantic-at-the-edge / Protocol-at-the-service-boundary allocation aligns with the framework's intended use.

8. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-04-29
   - Relevance: Establishes ports as the abstract interface the application offers to its surroundings, and adapters as the concrete translators between port shapes and external technologies. Grounds the Protocol-as-port allocation and the role of vendor-shaped types inside (and only inside) adapter implementations.

9. Domain-Driven Design — Eric Evans (Value Objects)
   - URL: <https://www.domainlanguage.com/ddd/>
   - Accessed: 2026-04-29
   - Relevance: Establishes value objects as immutable types defined by their attributes, used to express domain concepts that have no identity beyond their values. Grounds the choice of frozen dataclass for internal value types.

## Change Log

- 2026-05-08: Created. Establishes the allocation of Python type constructs to architectural boundaries: `typing.Protocol` for service contracts, `@dataclass(frozen=True)` for internal value types crossing package boundaries (including `OperationResult`), `pydantic.BaseModel` for trust-boundary input and schema-described output, `pydantic_settings.BaseSettings` for environment-variable configuration with `BaseModel` for nested sections, `typing.TypedDict` for dict-shaped vendor SDK payloads inside adapters, `enum.Enum` for closed semantic sets, and `typing.Literal` for type-level value constraints. The allocation is driven by the boundary at which the data lives, not by the data's shape.
