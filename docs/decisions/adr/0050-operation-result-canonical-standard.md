---
adr_id: ADR-0050
title: "Operation Result Canonical Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Transport and API
secondary_domains:
  - Dependency and Composition
  - Observability and Operations
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0045
impacts:
  - ADR-0060
  - ADR-0061
  - ADR-0063
supersedes:
  - ADR-0006
  - ADR-0020
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0048
related_packages: []
---

# Operation Result Canonical Standard

## Context

- Problem statement: The Operation Result pattern was documented in two legacy ADRs with different tier classifications: ADR-0006 was classified as Tier-1 Principle and contained extensive implementation detail (code examples, library comparisons, Railway-Oriented Programming philosophy), while ADR-0020 was classified as Tier-2 Standard and contained usage patterns for creating and handling results. This dual authority created confusion about whether the pattern is a foundational principle or an implementation standard, and which record to follow for practical guidance.
- Business/operational drivers:
  - Establish a single Tier-2 standard for the Operation Result pattern, eliminating duplicate authority.
  - Define clear boundary rules for where OperationResult is mandatory and where exceptions are appropriate.
  - Support uniform error handling across multiple integration providers (Google Workspace, AWS, GitHub, Slack).
  - Ensure transient vs. permanent error classification drives retry behavior consistently.
- Constraints:
  - OperationResult is used at integration boundaries, not throughout internal business logic (ADR-0045 Principle 2 — explicit DI means services are modular, but error handling strategy is a Tier-2 implementation choice).
  - The pattern must support typed metadata: status, error code, message, retry hints.
  - Callers must be able to map OperationResult status to HTTP status codes and platform-specific responses.
  - The pattern must remain provider-agnostic: business logic should not need to know which provider generated the result.
- Non-goals:
  - This record does not define the OperationResult class implementation details (field types, method signatures).
  - This record does not define HTTP response mapping conventions (delegated to ADR-0060).
  - This record does not mandate Railway-Oriented Programming; functional composition is an optional usage pattern.

## Decision

- Chosen approach: Establish OperationResult as a Tier-2 mandatory standard for integration boundaries, with clear scope boundaries for when to use Result vs. exceptions.
- Why this approach: The pattern is an implementation convention (Tier-2), not a foundational principle (Tier-1). It implements ADR-0045 Principle 3 (layer separation) by providing a uniform interface at the integration boundary, but the choice of Result type vs. exceptions is an implementation-level decision.

### Standard 1: Integration Boundary Mandate

All operations that cross integration boundaries (external API calls to Google Workspace, AWS, GitHub, Slack, and other third-party services) must return `OperationResult` instead of raising exceptions. This applies to all provider and integration service methods that make outbound API calls.

### Standard 2: Status Classification

OperationResult must classify outcomes using a minimal, domain-relevant status enumeration:

| Status | Semantics | Retry behavior |
|--------|-----------|----------------|
| `SUCCESS` | Operation completed successfully. | Not applicable. |
| `TRANSIENT_ERROR` | Retryable failure (rate limit, timeout, 5xx, network error). | Caller should retry with backoff; `retry_after` hint is mandatory. |
| `PERMANENT_ERROR` | Non-retryable failure (validation error, malformed request, 4xx). | Caller must not retry. |
| `UNAUTHORIZED` | Authentication or authorization failure. | Caller must not retry without credential refresh. |
| `NOT_FOUND` | Requested resource does not exist. | Caller must not retry for the same resource. |

### Standard 3: Structured Error Metadata

Every non-success result must include:
- `error_code`: a machine-readable string identifying the failure category (e.g., `RATE_LIMITED`, `UPSTREAM_TIMEOUT`).
- `message`: a human-readable description of the failure.
- `retry_after`: mandatory for `TRANSIENT_ERROR` status; seconds until retry is appropriate.

Provider and operation context must be available for structured logging.

### Standard 4: Exception Boundary Rule

OperationResult is mandatory only at integration boundaries. Internal application logic, business rules, and local validation should use Python exceptions. The boundary rule:

| Context | Error mechanism |
|---------|----------------|
| Integration boundary (external API calls) | OperationResult (mandatory). |
| Startup and initialization | Exceptions (fail-fast per ADR-0046 Invariant 3). |
| Internal business logic and validation | Exceptions (standard Python patterns). |
| Cross-layer service calls (internal) | Design choice; OperationResult permitted but not mandated. |

### Standard 5: Provider Agnosticism

Business logic that consumes OperationResult must not inspect provider-specific error details. The status classification (Standard 2) must be sufficient for all caller decisions. Provider-specific context (API error codes, HTTP status codes) is available only for logging and debugging, not for control flow.

### Standard 6: Functional Composition (Optional)

Railway-Oriented Programming composition methods (`map`, `bind`, `unwrap_or`) are available for chaining operations but are not mandatory. Their use is appropriate when multiple integration calls must be sequenced with automatic error short-circuiting. Overuse within internal business logic is an anti-pattern per the scope boundary in Standard 4.

## Alternatives Considered

1. Maintain two separate OperationResult ADRs:
   - Pros: Existing records are already in use.
   - Cons: Duplicate authority; ADR-0006 at Tier-1 contains implementation detail that violates ADR-0051 taxonomy.
   - Why not chosen: One canonical standard eliminates ambiguity.
2. Remove OperationResult and use only exceptions:
   - Pros: More Pythonic; no custom Result type needed.
   - Cons: Implicit control flow; poor type safety at integration boundaries; difficult to distinguish transient from permanent errors without per-provider exception hierarchies.
   - Why not chosen: The multi-provider integration model requires uniform error handling that exceptions do not provide.
3. Use a third-party Result library (dry-python/returns):
   - Pros: Feature-rich; community-maintained.
   - Cons: Heavy dependency; not tailored to integration boundary semantics.
   - Why not chosen: The custom OperationResult is simpler and domain-specific.
4. Promote OperationResult to Tier-1 Principle:
   - Pros: Maximum authority.
   - Cons: Implementation-level choice elevated above its appropriate governance tier; violates ADR-0051.
   - Why not chosen: The pattern is a standard implementation convention, not a foundational invariant.

## Consequences

- Positive impacts:
  - Single authoritative standard eliminates the ADR-0006 / ADR-0020 dual-authority problem.
  - Correct Tier-2 classification aligns with ADR-0051 taxonomy enforcement.
  - Clear boundary rule prevents OperationResult overuse in internal logic.
  - Uniform error handling enables provider-agnostic business logic.
- Tradeoffs accepted:
  - Custom OperationResult is not a Python stdlib type; team members must learn it.
  - More verbose than raw exceptions at integration boundaries, but provides structured metadata.
  - Functional composition is optional and may lead to inconsistent usage if not guided.
- Risks introduced:
  - Developers may use OperationResult for internal logic, violating Standard 4.
  - The five-status classification may be insufficient for future provider error semantics.
- Mitigations:
  - Code review enforcement of the boundary rule (Standard 4).
  - Status enumeration can be extended at Tier-2 without Tier-1 impact.

## Compliance and Boundaries

- Package/infrastructure boundary impact: OperationResult is returned by infrastructure integration services and consumed by application-layer code through the injection boundary (ADR-0048 Boundary 2).
- Type boundary impact: OperationResult itself is a `@dataclass(frozen=True)` at the internal service boundary; Pydantic models handle HTTP response mapping downstream (ADR-0060).
- Startup/plugin registration impact: Not directly applicable; startup failures use exceptions per Standard 4.
- Settings partitioning impact: Not directly applicable.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Rust Result type documentation (https://doc.rust-lang.org/std/result/).
  - Railway-Oriented Programming by Scott Wlaschin, including "Against Railway-Oriented Programming" (scope boundary guidance).
  - Python typing documentation for generic dataclass patterns.
  - Twelve-Factor App: Factor IV (Backing Services — uniform interface to external services).
  - OWASP error handling guidance.
- Alignment summary:
  - The pattern aligns with industry-standard Result types (Rust, Kotlin, Swift).
  - The boundary rule (integration boundaries only) aligns with Wlaschin's "Against ROP" guidance: domain errors use Result, infrastructure errors are case-by-case, panics use exceptions.
  - Provider agnosticism aligns with Factor IV (backing services as attached resources with uniform interface).
- Intentional deviations:
  - Python has no stdlib Result type; this is a custom implementation, which is standard practice in the Python community (dry-python/returns, rustedpy/result).

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0006 and ADR-0020 into one Tier-2 standard with correct taxonomy classification and clear boundary rules.
- Follow-up actions:
  - Mark ADR-0006 and ADR-0020 as superseded with `superseded_by: [ADR-0050]`.
  - Ensure ADR-0060 references this record in `constrained_by`.

## Source References

1. Source title: Railway-Oriented Programming
   - URL: https://fsharpforfunandprofit.com/rop/
   - Publisher/maintainer: Scott Wlaschin
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Original pattern description; functional composition methods.
2. Source title: Against Railway-Oriented Programming
   - URL: https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/
   - Publisher/maintainer: Scott Wlaschin
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Scope boundary guidance for when NOT to use Result; informs Standard 4.
3. Source title: Rust Result Type Documentation
   - URL: https://doc.rust-lang.org/std/result/
   - Publisher/maintainer: Rust project
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Industry-standard Result type; validates the pattern is not over-engineering.
4. Source title: Twelve-Factor App — Backing Services
   - URL: https://12factor.net/backing-services
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Factor IV supports uniform interface for external service interaction.
5. Source title: ADR-0006, ADR-0020 (Legacy)
   - URL: docs/decisions/adr/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source records being consolidated; OperationResult standards extracted and deduplicated.

## Implementation Guidance

- Required changes:
  - Mark ADR-0006 and ADR-0020 as `status: Superseded` and add `superseded_by: [ADR-0050]`.
  - Ensure all integration service methods return OperationResult, not raw exceptions.
  - Audit internal business logic for inappropriate OperationResult usage and refactor to exceptions where applicable.
- Validation and quality gates:
  - Test: integration methods return OperationResult with correct status classification.
  - Test: transient errors include retry_after metadata.
  - Test: provider-specific details do not leak into caller control flow.
  - ADR-0051 taxonomy check: confirm this is a Tier-2 Standard, not Tier-1 Principle.
- Test strategy and acceptance criteria impact:
  - Integration service tests must verify OperationResult contracts.
  - Business logic tests should use exceptions for internal error paths.

## Change Log

- 2026-04-28: Created canonical Tier-2 Operation Result standard; supersedes ADR-0006 and ADR-0020. Two source records consolidated into six standards with correct Tier-2 classification and clear boundary rules.
