---
adr_id: ADR-0046
title: "Runtime Lifecycle and Lifespan Canonical Model"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Runtime and Lifecycle
secondary_domains:
  - Package and Plugin Architecture
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
  - ADR-0049
  - ADR-0057
  - ADR-0058
  - ADR-0063
supersedes:
  - ADR-0005
  - ADR-0009
  - ADR-0011
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0049
related_packages: []
---

# Runtime Lifecycle and Lifespan Canonical Model

## Context

- Problem statement: Startup and shutdown lifecycle authority was fragmented across three legacy ADRs (ADR-0005, ADR-0009, ADR-0011), each describing overlapping aspects of the same lifecycle. ADR-0005 defined a 7-phase initialization sequence, ADR-0009 defined the FastAPI lifespan pattern, and ADR-0011 defined phase ordering constraints. This fragmentation created ambiguity about which record governed lifecycle behavior and allowed inconsistent phase definitions to coexist.
- Business/operational drivers:
  - Establish a single authoritative record for all startup and shutdown lifecycle invariants.
  - Ensure deterministic startup ordering so that configuration is available before services, services before plugins, and plugins before traffic.
  - Ensure graceful shutdown releases resources in reverse dependency order.
  - Eliminate duplicate lifecycle authority that creates conflicting guidance.
- Constraints:
  - FastAPI lifespan context manager is the sole entry point for startup/shutdown logic (ADR-0045 Principle 4).
  - ASGI lifespan protocol governs startup success/failure signaling to the container scheduler.
  - Startup must be deterministic and sequential; no concurrent phase execution.
  - Shutdown must complete within the container scheduler's termination grace period.
- Non-goals:
  - This record does not define specific phase implementations or code-level patterns.
  - This record does not specify which services or plugins are initialized in each phase.
  - This record does not define plugin registration mechanics (delegated to ADR-0049).

## Decision

- Chosen approach: Consolidate all lifecycle authority into one Tier-1 principle that defines lifecycle invariants without prescribing implementation details.
- Why this approach: A single lifecycle authority eliminates contradiction between the three source ADRs and provides a stable foundation for downstream standards (graceful shutdown, background services, plugin startup).

### Invariant 1: Single Lifecycle Entry Point

All startup and shutdown logic must execute through the FastAPI lifespan context manager. No startup or shutdown logic may execute via deprecated event handlers (`app.add_event_handler("startup", ...)` or `app.add_event_handler("shutdown", ...)`). Mixing lifespan with deprecated event handlers is prohibited.

### Invariant 2: Sequential Phase Execution

Startup must execute as a strict sequence of phases with explicit dependency ordering. No phase may begin until all preceding phases have completed successfully. The canonical phase ordering is:

1. **Configuration** — Load, validate, and freeze all settings.
2. **Infrastructure** — Initialize core platform services and capabilities.
3. **Discovery and Registration** — Discover and register plugins and providers.
4. **Feature Activation** — Activate feature-specific handlers, event subscribers, and integrations.
5. **Transport** — Start external transport connections (WebSocket, message queues).
6. **Background** — Start scheduled and background work (production only).

Phases may be refined or subdivided in Tier-2 standards, but the ordering invariant must be preserved.

### Invariant 3: Fail-Fast Startup

If any phase fails during startup, the lifespan must not reach the `yield` point. The ASGI server must send a `lifespan.startup.failed` event, and the process must exit with a non-zero status code. The container scheduler must not route traffic to a task that failed startup. Silent continuation after a startup failure is prohibited (constrained by ADR-0045 Principle 4).

### Invariant 4: Reverse-Order Graceful Shutdown

Shutdown must execute in reverse phase order. Background work stops first, then transport connections close, then features deactivate, then infrastructure services release resources. Shutdown must complete within the container scheduler's termination grace period. Resources acquired during startup must be released during shutdown; resource leaks are non-compliant.

### Invariant 5: Immutable Registries After Startup

All registries (plugin registries, provider registries, command registries) must be frozen after the startup sequence completes and before the application begins accepting traffic. Dynamic registration during request handling is prohibited.

### Invariant 6: Structured Lifecycle Observability

Each lifecycle phase transition must emit a structured log event with the phase name and transition outcome (started, completed, failed). These events form the minimum observability contract for operational monitoring and incident diagnosis.

## Alternatives Considered

1. Maintain three separate lifecycle ADRs with cross-references:
   - Pros: Smaller individual records; each addresses one aspect.
   - Cons: Overlapping authority creates contradiction risk; developers must consult three records to understand lifecycle behavior.
   - Why not chosen: Consolidation eliminates duplication and provides a single reference for lifecycle invariants.
2. Define lifecycle phases with implementation-level detail at Tier-1:
   - Pros: Complete guidance in one record.
   - Cons: Violates ADR-0044 one-authority-level-per-record rule; implementation changes would force Tier-1 amendments.
   - Why not chosen: Implementation details belong in Tier-2 standards.

## Consequences

- Positive impacts:
  - Single authoritative lifecycle record eliminates contradictions between ADR-0005, ADR-0009, and ADR-0011.
  - Deterministic startup ordering is now a governance-enforced invariant.
  - Fail-fast startup prevents silent degradation and aligns with ASGI protocol semantics.
- Tradeoffs accepted:
  - The six invariants are deliberately abstract; phase-specific implementation details require consulting Tier-2 standards.
  - New lifecycle phases require amending this Tier-1 record, which has higher change cost.
- Risks introduced:
  - The 6-phase model may not capture all future lifecycle needs (e.g., health-check warm-up phases).
- Mitigations:
  - The phase list is stated as a canonical ordering that may be refined or subdivided at Tier-2.
  - Future phases can be inserted between existing phases via Tier-2 standards without breaking the ordering invariant.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Lifecycle phases span both infrastructure (phases 1-2) and package (phases 3-4) layers; the boundary is the Discovery and Registration phase transition.
- Type boundary impact: Not directly applicable; deferred to ADR-0065.
- Startup/plugin registration impact: Invariant 3 (fail-fast) and Invariant 5 (immutable registries) directly constrain ADR-0049 plugin registration policy.
- Settings partitioning impact: Invariant 1 (configuration phase first) constrains ADR-0047 settings governance.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - FastAPI Lifespan Events documentation (https://fastapi.tiangolo.com/advanced/events/).
  - ASGI Lifespan Protocol v2.0 (startup.complete, startup.failed events).
  - Twelve-Factor App: Factor IX (Disposability — fast startup, graceful shutdown).
  - Starlette lifespan implementation details.
- Alignment summary:
  - Single lifespan entry point aligns with FastAPI's documented deprecation of startup/shutdown event handlers.
  - Fail-fast startup aligns with ASGI lifespan.startup.failed protocol and Factor IX.
  - Graceful shutdown in reverse order aligns with resource management best practices and Factor IX disposability.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0005, ADR-0009, and ADR-0011 into one lifecycle principle with no implementation leakage.
- Follow-up actions:
  - Mark ADR-0005, ADR-0009, and ADR-0011 as superseded with `superseded_by: [ADR-0046]`.
  - Ensure ADR-0049 references this record in `constrained_by`.

## Source References

1. Source title: FastAPI Lifespan Events
   - URL: https://fastapi.tiangolo.com/advanced/events/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Documents lifespan context manager as the recommended startup/shutdown mechanism.
2. Source title: ASGI Lifespan Protocol v2.0
   - URL: https://asgi.readthedocs.io/en/latest/specs/lifespan.html
   - Publisher/maintainer: ASGI community
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines startup.complete and startup.failed signaling semantics.
3. Source title: Twelve-Factor App — Disposability
   - URL: https://12factor.net/disposability
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Factor IX requires fast startup and graceful shutdown.
4. Source title: ADR-0005, ADR-0009, ADR-0011 (Legacy)
   - URL: docs/decisions/adr/superseded/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Source records being consolidated; lifecycle invariants extracted and implementation details removed.

## Implementation Guidance

- Required changes:
  - Mark ADR-0005, ADR-0009, ADR-0011 as `status: Superseded` and add `superseded_by: [ADR-0046]`.
  - Ensure downstream standards (ADR-0049, ADR-0057, ADR-0058) reference this record in `constrained_by`.
- Validation and quality gates:
  - ADR-0051 taxonomy check: confirm no implementation-level code examples or phase-specific logic in this record.
  - Metadata completeness check: all 18 fields populated.
- Test strategy and acceptance criteria impact:
  - No direct test changes; lifecycle invariants are validated through downstream standard and integration test compliance.

## Change Log

- 2026-04-28: Created canonical Tier-1 lifecycle principle; supersedes ADR-0005, ADR-0009, ADR-0011. Three source records consolidated into six lifecycle invariants with no implementation detail.
