---
adr_id: ADR-0043
title: "Access Admin Operator Stuck-Lock Scope"
status: Proposed
decision_type: Feature
tier: Tier-4
date_created: 2026-04-27
last_updated: 2026-04-27
last_reviewed: 2026-04-27
next_review_due: 2026-08-25
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records: []
related_packages: []
review_state: current
---
# Access Admin Operator Stuck-Lock Scope

## Metadata

- Title: Access Admin Operator Stuck-Lock Scope
- ID: tier-4-12
- Status: Proposed (Tentative)
- Scope: Tier-4 Application
- Date Created: 2026-04-27
- Last Updated: 2026-04-27
- Last Reviewed: 2026-04-27
- Next Review Due: 2026-07-27
- Owners: Platform Engineering
- Related Records: tier-4-01, tier-4-02, tier-4-09, tier-4-10, tier-1-foundation/application-lifecycle/09
- Related Features/Packages: app/packages/access/admin, app/packages/access/sync

## Context

- Problem statement: Access Sync can leave a running lock record after abrupt process restart or interrupted execution, blocking subsequent sync requests until stale-threshold fallback is reached.
- Business/operational drivers: SRE operators need a safe, auditable, in-product intervention path for immediate lock release instead of ad-hoc local scripts.
- Constraints:
  - Keep phase 1 scope intentionally small and focused.
  - Preserve feature boundaries: sync lock intervention belongs to access feature context.
  - Maintain deterministic authorization, auditability, and stable API/command error semantics.
- Non-goals:
  - This record does not introduce an app-wide centralized admin control plane.
  - This record does not redesign Access Sync reconciliation behavior.
  - This record does not add Slack modal/action workflows in phase 1.

## Decision

- Chosen approach:
  - Add one focused operator operation under access/admin to release stuck Access Sync running locks (platform lock or user lock).
  - Keep this operation feature-scoped within access/admin interactions, ingress, and application orchestration.
  - Defer app-wide reusable admin central service to a future ADR once multiple features demonstrate common admin operation requirements.
- Why this approach:
  - Solves a concrete operational pain immediately.
  - Minimizes architecture risk and avoids premature cross-feature abstraction.
  - Preserves clear ownership and bounded context in the access domain.
- Principles established:
  - Prefer narrow, proven admin operations over speculative platform-wide admin frameworks.
  - Promote to shared core only after repeated, validated cross-feature reuse patterns.

## Alternatives Considered

1. Introduce centralized app-level admin service now:
   - Pros: Single place for admin UX patterns and authorization plumbing.
   - Cons: Higher immediate complexity; unclear shared requirements; risk of over-generalization.
   - Why not chosen: Current requirement is narrow and access-domain specific.
2. Keep script-only operational workaround:
   - Pros: No application changes.
   - Cons: Weak auditability, inconsistent operator experience, higher manual error risk.
   - Why not chosen: Does not meet long-term reliability and governance expectations.

## Consequences

- Positive impacts:
  - Immediate, auditable remediation for stuck lock states.
  - Reduced operator dependence on local scripts and direct table editing.
  - Retains architectural clarity in feature boundaries.
- Tradeoffs accepted:
  - Duplicate admin interaction patterns may exist temporarily until broader admin needs justify extraction.
- Risks introduced:
  - Potential future refactor when centralized admin service becomes justified.
- Mitigations:
  - Keep operation contract narrow and typed.
  - Isolate reusable pieces (authorization policy contract, audit envelope) without introducing a full shared admin core.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - Operation is owned by app/packages/access/admin and uses infrastructure services via providers.
  - No new cross-feature dependency edges are introduced.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - BaseModel for HTTP and Slack boundary payloads.
  - frozen dataclass for canonical lock release operation and audit event data.
  - Protocol for repository/service contracts.
- Startup/plugin registration impact:
  - No import-time side effects.
  - Existing package startup/warmup and hookimpl registration patterns remain unchanged.
- Settings partitioning impact:
  - Access admin settings continue to reside in access feature settings slice.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 30 days: No
- If Yes, web validation completed: No
- Validation summary: Local architecture decisions aligned to accepted project ADRs.
- Follow-up actions:
  - Re-evaluate central admin service extraction only after at least two additional feature admin operations exist.

## Source References

1. Source title: Access Admin Feature Architecture (transition packet)
   - URL: docs/transition/access-admin/access-admin-architecture.md
   - Publisher/maintainer: Platform Engineering
   - Accessed date (YYYY-MM-DD): 2026-04-27
   - Relevance summary: Defines current access/admin phase 1 boundaries and accepted design decisions.
2. Source title: Access Admin ADR Compliance Gap Map
   - URL: docs/transition/access-admin/access-admin-adr-gap-map.md
   - Publisher/maintainer: Platform Engineering
   - Accessed date (YYYY-MM-DD): 2026-04-27
   - Relevance summary: Captures transition from old concept to ADR-aligned target and open standardization items.
3. Source title: Access Sync lock handling implementation
   - URL: app/packages/access/sync/platform_lock.py
   - Publisher/maintainer: Application Engineering
   - Accessed date (YYYY-MM-DD): 2026-04-27
   - Relevance summary: Confirms stale-lock and running-lock semantics to be supported by the operator intervention path.
4. Source title: Existing manual unlock operational script
   - URL: app/bin/unlock-sync-job.sh
   - Publisher/maintainer: Application Engineering
   - Accessed date (YYYY-MM-DD): 2026-04-27
   - Relevance summary: Demonstrates concrete operational need for first-class lock release operation.

## Implementation Guidance

- Required changes:
  - Add focused lock-release operation contracts in access/admin interaction and application layers.
  - Support platform lock and user lock targets.
  - Enforce admin authorization and immutable audit metadata for each intervention.
  - Return stable error mapping for not-found and non-running lock targets.
- Validation and quality gates:
  - mypy
  - flake8
  - black --check .
  - pytest app/tests --ignore=app/tests/smoke
- Test strategy and acceptance criteria impact:
  - Add failing tests first for HTTP and Slack lock-release paths, authorization checks, and deterministic repeat behavior.
  - Add service-layer tests for lock state transitions and audit emission.

## Change Log

- 2026-04-27: Created tentative Tier-4 ADR to scope access/admin operator interventions to stuck-lock release only and defer app-level centralized admin service.
