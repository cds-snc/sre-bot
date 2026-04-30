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
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
 - ADR-0044
 - ADR-0045
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
 - ADR-0039
 - ADR-0055
 - ADR-0056
 - ADR-0062
 - ADR-0077
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
- Every Protocol-backed service (Category A per ADR-0077) must have a dev/test fallback implementation.

### Dev/Test Fallback Standard for Category A Services

Every Category A service (ADR-0077 Standard 1) must provide a dev-safe fallback implementation that can run without cloud credentials or external service access. This enables:

1. **Local development** — developers start the app without AWS credentials, Google OAuth tokens, or SQS queues.
2. **CI testing** — automated tests run against in-memory implementations without provisioning cloud resources.
3. **Cloud portability** — configurable backends (ADR-0045 P7) require at least two implementations: the production backing service and the dev/test fallback.

#### Fallback Rules

| # | Rule | Rationale |
|---|------|-----------|
| F1 | Every Category A service must have an in-memory or local fallback implementation that satisfies the same Protocol contract | Dev/test environments must be able to start and run the full application without cloud credentials |
| F2 | The fallback must be selectable via the `*_BACKEND` settings key (ADR-0055 Standard 9) with a dev-safe default value (typically `"memory"`) | Configuration-driven, not code-driven (ADR-0047 P6) |
| F3 | The fallback must provide functionally equivalent behavior for the Protocol's public interface — data persists for the process lifetime but is not required to survive restarts | Behavioral parity for testing; durability is a production concern |
| F4 | The fallback must not import cloud SDKs, external service clients, or production-only dependencies | CI must run without installing cloud provider libraries |
| F5 | The fallback must be usable as a test double via `dependency_overrides` (ADR-0077 Standard 4) | Clean test fixtures without mock patches |

#### Current Category A Fallback Status

| Service | Fallback Exists? | Fallback Type | Notes |
|---------|-----------------|---------------|-------|
| `DirectoryProvider` | No | — | Needs in-memory directory stub |
| `RetryStore` | Yes | `InMemoryRetryStore` | Reference implementation |
| `RetryProcessor` | Yes | Feature-specific in-memory | — |
| `ResponseChannel` | Yes | Platform-specific test stubs | — |
| `BackgroundJobRegistry` | Yes | In-memory scheduler | — |
| `StorageService` | No | — | Needs in-memory key-value store |
| `IdentityService` | No | — | Needs stub identity resolver |
| `AuditTrailService` | No | — | Needs in-memory audit log |
| `NotificationService` | No | — | Needs no-op or in-memory notification sink |
| `IdempotencyService` | No | — | Needs in-memory idempotency store |

**Migration note:** Fallback implementations are created during the ADR-0077 Protocol migration (Standard 5, step 6). Each Protocol migration includes creating the in-memory fallback. The fallback is then wired into the provider via ADR-0056 Standard 8 backend-selection logic.

## Alternatives Considered

1. Keep parity/log guidance distributed across older ADRs and runbooks.

- Pros: Minimal editing overhead.
- Cons: Conflicting authority and weak enforceability.
- Why not chosen: Step 5 requires explicit ownership of Twelve-Factor gaps.

1. Couple logging retention/indexing policy into application ADRs.

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
- Runtime request-context propagation is not yet fully wired end-to-end; correlation IDs may be absent from some structured log entries until explicit middleware binding is added.
- Structured log events may inadvertently serialize secrets or privileged payloads (tokens, credentials, PII) into stdout/stderr streams that the platform then archives. This is a high-impact risk given the platform's multi-provider integration surface.
- Mitigations:
- Track temporary deviations in Tier-5 migration ADRs with explicit retirement dates.
- Add request-boundary middleware that guarantees `clear_contextvars` and `bind_contextvars` on every request.
- Define and enforce log-safety review checks (explicit redaction verification) before structured log changes reach production.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
- Packages emit structured events; infrastructure logging layer handles enrichment and transport handoff.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
- Not applicable.
- Startup/plugin registration impact:
- Startup behavior must remain parity-consistent between dev and production modes.
- Settings partitioning impact:
- Logging and parity controls belong in infrastructure/server settings slices and must be environment-driven.
- Dev/test fallback impact: The fallback standard requires every Category A service (ADR-0077) to provide an in-memory implementation selectable via `*_BACKEND` settings (ADR-0055 Standard 9). This extends dev/prod parity from runtime behavior to service implementation — dev and prod use the same Protocol contract and provider graph, differing only in the concrete implementation behind the Protocol. Provider factory logic is governed by ADR-0056 Standard 8.

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
- Validation summary: Twelve-Factor parity/log ownership gap is now explicitly covered at Tier-2. Amended 2026-04-30 to add dev/test fallback standard for Category A services per ADR-0045 P7.
- Follow-up actions:
- Align remaining logging and parity ADR references to this canonical standard.

## Source References (Required)

1. Source title: The Twelve-Factor App - Dev/Prod Parity

- URL: <https://12factor.net/dev-prod-parity>
- Publisher/maintainer: 12factor contributors
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Defines minimizing environmental divergence.

1. Source title: The Twelve-Factor App - Logs

- URL: <https://12factor.net/logs>
- Publisher/maintainer: 12factor contributors
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Defines logs as event streams managed by execution environment.

1. Source title: Logging Standards (OpenTelemetry + structlog)

- URL: docs/decisions/adr/superseded/0029-logging-standards.md
- Publisher/maintainer: SRE Team
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Legacy logging baseline being superseded by this canonical ownership standard.

## Implementation Guidance

- Required changes:
- Keep development runtime paths close to production for dependencies and startup flow.
- Emit structured logs to stdout/stderr; do not embed sink-specific application logic.
- Add or verify request-boundary middleware that calls `structlog.contextvars.clear_contextvars()` at the start of each request and binds correlation context (request ID, method, path) before any downstream processing occurs. This must be wired into the live FastAPI runtime, not only used in tests.
- Audit all structured log call sites for sensitive field emission; add explicit redaction for tokens, credentials, and PII before any new logging path is merged.
- Validation and quality gates:
- Validate parity-critical settings in CI and local bootstrap checks.
- End-to-end context propagation test: a request must produce log entries that contain the bound request ID from first middleware to final response handler.
- Log-safety gate: structured log output for access-request, sync, and multi-provider operations must be reviewed for secret redaction before shipping.
- Test strategy and acceptance criteria impact:
- Include tests that verify logging context propagation (correlation ID present in every structured log entry for a given request) and parity-sensitive configuration handling.
- Acceptance test: a fabricated request with a known request ID must produce at least one structured log entry containing that ID, with no credential fields serialized.

## Change Log

- 2026-04-28: Added Tier-2 standard for Twelve-Factor dev/prod parity and logs ownership; superseded ADR-0029.
- 2026-04-28: Strengthened risks and implementation guidance following challenge review; named sensitive-data leak as explicit risk, made middleware context binding a required change, and elevated redaction verification to a required gate.
- 2026-04-30: Dev/test fallback standard amendment. Added Category A fallback requirement: every Protocol-backed service must have an in-memory or local fallback implementation selectable via `*_BACKEND` settings. Defines 5 rules (F1-F5) and current fallback status for all 10 Category A services. Cross-references ADR-0045 P7, ADR-0055 S9, ADR-0056 S8, ADR-0077 S1/S4/S5. See managed-services-delegation-adr-review-tracker-2026-04-30.md Item #9.
