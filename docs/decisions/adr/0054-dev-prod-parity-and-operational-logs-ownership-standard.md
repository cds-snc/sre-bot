---
adr_id: ADR-0054
title: "Dev/Prod Parity and Operational Logs Ownership Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Observability and Operations
secondary_domains:
  - Delivery and Environment Parity
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0051
impacts:
  - ADR-0062
  - ADR-0063
  - ADR-0064
supersedes:
  - ADR-0029
superseded_by: []
review_state: current
related_records:
  - ADR-0031
  - ADR-0039
related_packages:
  - app/infrastructure/logging
---
## Context

- Problem statement: Dev/prod parity and log-stream ownership were partially covered and fragmented, causing ambiguity in operational expectations.
- Business/operational drivers:
  - Reduce environment surprises by aligning runtime behavior across development and production.
  - Ensure logs are emitted and handled as event streams with clear ownership boundaries.
- Constraints:
  - Must align with Twelve-Factor factors X (dev/prod parity) and XI (logs).
  - Must preserve request-context propagation and structured logging posture.
- Non-goals:
  - This record does not replace feature-specific logging field definitions.

## Decision

- Chosen approach:
  - Define parity requirements for dependencies, startup path, and operational controls between dev and prod.
  - Treat application logs as unbuffered event streams written to standard output/error.
  - Keep log transport, retention, and indexing as platform concerns external to feature packages.
  - Require structured log events with contextual metadata and no sensitive secret emission.
- Why this approach:
  - Makes behavior reproducible during incidents and keeps application responsibility limited to event emission quality.
- Principles established:
  - Parity is mandatory for critical runtime behavior.
  - App emits logs; platform routes and stores logs.

## Alternatives Considered

1. Keep parity/log guidance distributed across older ADRs and runbooks.
   - Pros: Minimal editing overhead.
   - Cons: Conflicting authority and weak enforceability.
   - Why not chosen: Step 5 requires explicit ownership of Twelve-Factor gaps.
2. Couple logging retention/indexing policy into application ADRs.
   - Pros: Single document for all logging concerns.
   - Cons: Blurs platform vs application ownership and increases churn.
   - Why not chosen: Violates clear boundary model.

## Consequences

- Positive impacts:
  - Faster troubleshooting due to consistent environment behavior.
  - Cleaner logging boundary between application and platform responsibilities.
- Tradeoffs accepted:
  - Requires stricter discipline in local/dev runtime parity and configuration management.
- Risks introduced:
  - Existing local workflows may rely on shortcuts not suitable for parity.
- Mitigations:
  - Track temporary deviations in Tier-5 migration ADRs with explicit retirement dates.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - Packages emit structured events; infrastructure logging layer handles enrichment and transport handoff.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - Not applicable.
- Startup/plugin registration impact:
  - Startup behavior must remain parity-consistent between dev and production modes.
- Settings partitioning impact:
  - Logging and parity controls belong in infrastructure/server settings slices and must be environment-driven.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor factors X and XI.
  - Existing repository logging standards and request-context guidance.
- Alignment summary:
  - Decision aligns to parity expectations and event-stream logging ownership boundaries.
- Intentional deviations:
  - None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Twelve-Factor parity/log ownership gap is now explicitly covered at Tier-2.
- Follow-up actions:
  - Align remaining logging and parity ADR references to this canonical standard.

## Source References (Required)

1. Source title: The Twelve-Factor App - Dev/Prod Parity
   - URL: https://12factor.net/dev-prod-parity
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines minimizing environmental divergence.
2. Source title: The Twelve-Factor App - Logs
   - URL: https://12factor.net/logs
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines logs as event streams managed by execution environment.
3. Source title: Logging Standards (OpenTelemetry + structlog)
   - URL: docs/decisions/adr/0029-logging-standards.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Legacy logging baseline being superseded by this canonical ownership standard.

## Implementation Guidance

- Required changes:
  - Keep development runtime paths close to production for dependencies and startup flow.
  - Emit structured logs to stdout/stderr; do not embed sink-specific application logic.
- Validation and quality gates:
  - Validate parity-critical settings in CI and local bootstrap checks.
  - Audit structured logs for required context and secret redaction.
- Test strategy and acceptance criteria impact:
  - Include tests that verify logging context propagation and parity-sensitive configuration handling.

## Change Log

- 2026-04-28: Added Tier-2 standard for Twelve-Factor dev/prod parity and logs ownership; superseded ADR-0029.
