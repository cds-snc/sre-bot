---
adr_id: ADR-0052
title: "Build-Release-Run Delivery Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Delivery and Environment Parity
secondary_domains:
  - Runtime and Lifecycle
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
  - ADR-0053
  - ADR-0054
  - ADR-0063
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0046
related_packages:
  - app/server
---
## Context

- Problem statement: Build, release, and run responsibilities were not codified in one authoritative ADR, leading to ad hoc deployment behavior.
- Business/operational drivers:
  - Stabilize release quality while the team remains single-threaded.
  - Reduce risk from undocumented environment drift between build and runtime.
- Constraints:
  - Standard must be usable in local and CI execution paths.
  - Must align with Twelve-Factor factor V (Build, Release, Run).
- Non-goals:
  - This record does not select a CI vendor or a specific deployment platform.

## Decision

- Chosen approach:
  - Adopt explicit separation between build, release, and run phases.
  - Build phase produces immutable, versioned artifacts with dependency lock information.
  - Release phase binds configuration and deployment metadata to a specific artifact version.
  - Run phase executes only released artifacts and must not rebuild code in production execution paths.
- Why this approach:
  - Preserves reproducibility and enables deterministic rollback behavior.
- Principles established:
  - Build once per versioned artifact.
  - Release metadata is explicit and auditable.
  - Runtime execution consumes immutable release outputs.

## Alternatives Considered

1. Combine build and run in each environment.
   - Pros: Minimal process overhead.
   - Cons: Non-deterministic behavior and hard-to-audit releases.
   - Why not chosen: Violates Twelve-Factor separation.
2. Keep delivery process documented only in runbooks.
   - Pros: Flexible text updates.
   - Cons: Weak architecture authority and no ADR-level traceability.
   - Why not chosen: Step 5 requires explicit ADR ownership for this concern.

## Consequences

- Positive impacts:
  - Release pipelines become easier to reason about and audit.
  - Rollback and incident analysis improve due to clear artifact lineage.
- Tradeoffs accepted:
  - More explicit release metadata management is required.
- Risks introduced:
  - Legacy jobs may still combine phases until migrated.
- Mitigations:
  - Phase legacy delivery paths behind Tier-5 migration ADRs where needed.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - No direct package logic change; standard constrains deployment behavior for the whole platform.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - Not applicable.
- Startup/plugin registration impact:
  - Runtime startup should operate on released artifacts only.
- Settings partitioning impact:
  - Release phase binds environment-specific settings without mutating built artifacts.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor factor V (build, release, run separation).
  - CI/CD release-readiness guidance for deterministic deployments.
- Alignment summary:
  - Decision aligns to immutable artifact and separated release-stage responsibilities.
- Intentional deviations:
  - None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Build-release-run ownership now has explicit Tier-2 standard authority.
- Follow-up actions:
  - Ensure release automation references this ADR during pipeline updates.

## Source References (Required)

1. Source title: The Twelve-Factor App - Build, Release, Run
   - URL: https://12factor.net/build-release-run
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines strict separation of build, release, and run stages.
2. Source title: Continuous Integration
   - URL: https://martinfowler.com/articles/continuousIntegration.html
   - Publisher/maintainer: Martin Fowler
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Supports release-readiness and repeatable integration/build practices.
3. Source title: ADR Taxonomy and Classification Enforcement Standard
   - URL: docs/decisions/adr/0051-adr-taxonomy-and-classification-enforcement-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Provides Tier-2 taxonomy constraints for this delivery standard.

## Implementation Guidance

- Required changes:
  - Keep build, release, and run responsibilities distinct in CI/CD workflows and operational runbooks.
  - Track release identifiers independent of source branch names.
- Validation and quality gates:
  - Verify artifact immutability and reproducibility checks in CI.
  - Confirm runtime deployment consumes a released artifact digest/version.
- Test strategy and acceptance criteria impact:
  - Delivery tests should verify release metadata resolution and rollback viability.

## Change Log

- 2026-04-28: Added Tier-2 standard covering Twelve-Factor build-release-run ownership for Phase A execution.
