---
adr_id: ADR-0053
title: "Port Binding and Runtime Exposure Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Delivery and Environment Parity
secondary_domains:
  - Transport and API
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0051
  - ADR-0052
impacts:
  - ADR-0063
  - ADR-0064
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0033
  - ADR-0039
related_packages:
  - app/server
---
## Context

- Problem statement: Port exposure and runtime binding behavior were implicit across server and deployment layers, increasing configuration drift risk.
- Business/operational drivers:
  - Define one stable contract for service exposure in every environment.
  - Avoid environment-specific hardcoding of network bind settings.
- Constraints:
  - Must align with Twelve-Factor factor VII (Port Binding).
  - Must support containerized and non-containerized runtime paths.
- Non-goals:
  - This record does not define ingress/load-balancer vendor specifics.

## Decision

- Chosen approach:
  - Services expose themselves via a configured runtime port and host binding contract.
  - Runtime bind target is supplied through environment configuration (for example `PORT`), not source changes.
  - Health and readiness probes must operate through the same externally exposed service interface.
  - Internal admin endpoints must remain explicitly scoped and not piggyback on undocumented side ports.
- Why this approach:
  - Makes service exposure predictable across local, CI preview, and production environments.
- Principles established:
  - Port binding is application responsibility.
  - Exposure contract is configuration-driven and environment-agnostic.

## Alternatives Considered

1. Hardcode bind host/port by environment profile.
   - Pros: Simple implementation in one code path.
   - Cons: Drift-prone and brittle across deployment targets.
   - Why not chosen: Violates Twelve-Factor port-binding expectations.
2. Rely solely on external wrappers to expose the service.
   - Pros: App code remains minimal.
   - Cons: Runtime exposure contract is hidden and less testable.
   - Why not chosen: Ownership must remain explicit in architecture records.

## Consequences

- Positive impacts:
  - Reduced ambiguity in environment-specific runtime wiring.
  - Better portability and clearer operations diagnostics.
- Tradeoffs accepted:
  - Requires consistent deployment configuration for bind values.
- Risks introduced:
  - Legacy startup scripts may assume implicit defaults.
- Mitigations:
  - Track migration via Tier-5 decisions where legacy scripts need transition windows.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - No business-domain changes; this governs server/runtime exposure policy.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - Not applicable.
- Startup/plugin registration impact:
  - Startup checks should validate exposure configuration before serving traffic.
- Settings partitioning impact:
  - Bind settings belong in infrastructure/server settings and should be injected as config.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor factor VII (port binding)
  - FastAPI deployment/runtime guidance for externally served applications
- Alignment summary:
  - Decision aligns with application-owned service exposure and env-driven bind configuration.
- Intentional deviations:
  - None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Port-binding concern now has explicit Tier-2 ownership and compatibility with current server architecture.
- Follow-up actions:
  - Validate deployment manifests and local runtime commands use the same bind contract.

## Source References (Required)

1. Source title: The Twelve-Factor App - Port Binding
   - URL: https://12factor.net/port-binding
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines self-contained app exposure via bound ports.
2. Source title: FastAPI Deployment Concepts
   - URL: https://fastapi.tiangolo.com/deployment/concepts/
   - Publisher/maintainer: FastAPI maintainers
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Provides runtime/deployment expectations for exposing FastAPI services.
3. Source title: Build-Release-Run Delivery Standard
   - URL: docs/decisions/adr/0052-build-release-run-delivery-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Constrains runtime exposure behavior to released artifacts and environment configuration.

## Implementation Guidance

- Required changes:
  - Standardize runtime bind environment variables and defaults in server settings.
  - Ensure health/readiness endpoints are reachable through the declared service interface.
- Validation and quality gates:
  - Validate runtime startup fails clearly when bind configuration is invalid.
  - Confirm deployment manifests set bind parameters explicitly.
- Test strategy and acceptance criteria impact:
  - Route and startup tests should cover valid and invalid bind configuration paths.

## Change Log

- 2026-04-28: Added Tier-2 standard for Twelve-Factor port binding ownership and runtime exposure contract.
