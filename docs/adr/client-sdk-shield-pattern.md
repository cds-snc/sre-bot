---
title: "Client SDK Shield Pattern"
status: Draft
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, operation-result-pattern.md, client-adapter-responsibilities.md, outbound-retry-policy.md]
date: 2026-05-12
decision_makers:
  - SRE Team
---

# Client SDK Shield Pattern

## Context and Problem Statement

Feature code should not hold vendor SDK concerns such as retry loops, transport error classes, or credential wiring. At the same time, engineers need ergonomic access to SDK capabilities without maintaining a huge mirror wrapper every time a vendor adds a new API method.

The problem this record addresses: **how to wrap vendor SDK usage behind a resilient boundary without leaking raw SDK semantics into feature/services or creating a brittle, over-abstracted mirror of the entire SDK surface.**

**Constraints:**

- The shield is a vendor-client boundary concern, not a feature-domain concern.
- The shield returns `OperationResult` at the client boundary, per `client-adapter-responsibilities.md`.
- Domain interpretation remains in adapters/services above the client boundary.
- Retry behavior must align with provider semantics (e.g., `Retry-After` and SDK retry modes), not arbitrary local loops.
- Inbound Slack/Bolt listener constraints (for example, 3-second `ack()` timing) still apply and are not bypassed by this pattern.

**Non-goals:**

- This record does not redefine `OperationResult` shape or statuses.
- This record does not define per-feature adapter behavior.
- This record does not require wrapping every SDK method as a first-class facade method.

## Considered Options

**Option 1 - Generic pass-through shield (`execute(method, *args, **kwargs)`) exposed to feature code.**

Maximum flexibility with low wrapper maintenance, but high risk of boundary leakage and inconsistent domain mapping.

**Option 2 - Curated shield facade per capability (preferred).**

Expose explicit client methods for stable capabilities, and optionally allow a constrained escape hatch inside adapter files only.

**Option 3 - No shield, adapters call SDK directly.**

Simple initially, but duplicates resilience and error mapping logic across adapters.

## Decision Outcome

**Chosen: Option 2 - curated shield facade with constrained escape hatch.**

The shield pattern is valid when treated as a **resilience and transport-classification boundary**, not as a universal SDK tunnel.

### Guardrails

- Shield methods return `OperationResult` and never raise SDK exceptions above the client boundary.
- Transport concerns stay in the shield: retries, backoff, timeout handling, and typed exception classification.
- Adapters/services above the shield interpret statuses in domain terms; they do not parse SDK exceptions.
- A generic `execute(...)` may exist only for migration or uncommon endpoints, and must be consumed from adapter files, not feature service/domain code.
- New recurring operations should graduate from generic `execute(...)` to named facade methods for auditability and stable typing.

### Slack-specific implications

- Respect Slack rate-limit behavior: 429 handling and `Retry-After`.
- Use SDK retry primitives where available (`RetryHandler`, `RateLimitErrorRetryHandler`, async variants).
- Keep listener `ack()` timing independent from outbound retries; acknowledge fast, then do longer work asynchronously.

## Consequences

**Positive:**

- Centralized resilience and error mapping.
- Lower adapter duplication.
- Better replaceability across SDK/version/provider changes.
- Better operational consistency for retry and throttling behavior.

**Tradeoffs accepted:**

- Client layer gains complexity.
- Requires clear guardrails to prevent generic pass-through misuse.
- Some vendor-specific nuances still require explicit facade design.

**Risks:**

- Overuse of generic `execute(...)` can leak vendor coupling upward.
- Incorrect retry layering can double-retry and increase latency.

## Confirmation

Compliance is verified by:

- Client review: methods return `OperationResult`; no SDK exception escapes.
- Adapter review: adapters interpret status, not SDK exception classes.
- Import review: domain/service modules do not import vendor SDK modules.
- Tests:
  - Client executor tests for retry classification and `OperationResult` mapping.
  - Adapter tests for domain interpretation of each status.

## Source References

1. Slack Bolt for Python - Acknowledging requests
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/>
   - Accessed: 2026-05-12
   - Relevance: Confirms 3-second acknowledgement constraint, requiring quick `ack()` and decoupled long-running work.

2. Slack Web API - Rate limits
   - URL: <https://docs.slack.dev/apis/web-api/rate-limits/>
   - Accessed: 2026-05-12
   - Relevance: Confirms 429 behavior and `Retry-After` semantics that shield-level retry logic must honor.

3. Python Slack SDK - Web client / RetryHandler
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/web/>
   - Accessed: 2026-05-12
   - Relevance: Documents built-in retry handlers and async retry support; shield should compose with SDK capabilities, not fight them.

4. Boto3 - Retries
   - URL: <https://docs.aws.amazon.com/boto3/latest/guide/retries.html>
   - Accessed: 2026-05-12
   - Relevance: Confirms SDK-provided retry modes (legacy/standard/adaptive) and retry semantics that should inform client-layer policy.

5. The Twelve-Factor App - Backing Services
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-05-12
   - Relevance: Supports treating vendor services as attachable resources behind stable application-facing boundaries.

6. Architecture Patterns with Python - Repository Pattern
   - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
   - Accessed: 2026-05-12
   - Relevance: Reinforces dependency inversion and boundary-focused abstractions, including tradeoff awareness for added indirection.

## Change Log

- 2026-05-12: Created. Defines the Shield Pattern as a constrained vendor-client facade with resilience and transport-level classification at the client boundary, plus guardrails to prevent boundary leakage from generic pass-through SDK execution.
