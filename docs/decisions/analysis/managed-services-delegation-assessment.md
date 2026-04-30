# Managed Services Delegation Codebase Assessment

**Date:** 2026-04-30  
**Related ADRs:** ADR-0045 P7, ADR-0077, ADR-0079  
**Purpose:** Codebase audit of build-vs-delegate decisions and component migration roadmap

---

## 1. Codebase Audit: Build vs. Delegate

### Correctly Delegated (Thin Wrappers)

| Component | Approach | LOC |
|-----------|----------|-----|
| Background scheduling | `schedule` library + pluggy adapter | ~50 |
| Rate limiting | WAF → ALB → `slowapi` library | ~100 |
| HTTP client | `requests.Session` wrapper | ~150 |
| AWS clients | Thin `boto3` facades | Minimal |
| Google Workspace clients | Thin `google-api-python-client` facades | Minimal |
| Distributed locks | DynamoDB conditional writes (native primitive) | ~100 |
| Settings validation | `pydantic.BaseSettings` | — |

### Custom Code Warranting Scrutiny

| Component | Custom LOC | What's Reimplemented | Available Alternative | Assessment |
|-----------|-----------|---------------------|----------------------|------------|
| **Circuit breaker** | ~250–300 | Full 3-state machine (CLOSED/OPEN/HALF_OPEN), thread-safe transitions, half-open rate limiting | `pybreaker` — mature, observability hooks | Replace (Tier-5 ADR needed) |
| **Retry orchestration** | ~600–700 | Exponential backoff, attempt tracking, batch processing, multi-backend store | `tenacity` for in-process retry; DynamoDB store has no library equivalent | Replace in-process portion (Tier-5 ADR needed); keep DynamoDB store |
| **Event dispatcher** | ~300 | Handler registry, thread-pool dispatch, wildcard matching, correlation propagation | `blinker`, `pyee` | Keep — proportional, simple. Fix import-time side effects (ADR-0079 S2) |
| **Idempotency** | ~200–250 | DynamoDB-backed dedup cache with TTL | AWS Lambda Powertools `idempotency` | Keep — proportional. Evaluate if complexity grows |

---

## 2. Component Migration Roadmap

| Concern | Current Tier | Target Tier | Action | Priority |
|---------|-------------|-------------|--------|----------|
| Circuit breaker | 3 (custom) | 2 (`pybreaker`) | Replace incrementally | Medium — Tier-5 ADR |
| In-process retry | 3 (custom) | 2 (`tenacity`) | Replace when use sites are next touched | Medium — Tier-5 ADR |
| DynamoDB retry store | 1 (managed) | 1 (keep) | No change | — |
| Event dispatcher | 3 (custom) | 3 (keep, fix violations) | Fix ADR-0048 B4 import-time side effects | High — ADR-0079 S2 |
| Distributed locks | 1 (managed) | 1 (keep) | No change | — |
| Idempotency | 1 (managed) | 1 (keep) | Evaluate later | Low |
| Queue/messaging | N/A | 1 (SQS) | Defer until concrete need; wrap SQS, don't build custom | Deferred |

---

## 3. ADR-0079 Overreach Analysis

ADR-0079 originally conflated two concerns:

**Concern A — Event Dispatcher Cleanup (Standard 2):** Legitimate remediation of import-time side effects. Well-scoped, aligned with ADR-0048 B4. Proceeded independently.

**Concern B — Speculative Queue Architecture (Standards 1, 3–6):** Defined custom Protocol contracts for message broker operations that are the core value proposition of managed services (SQS, EventBridge). The application should wrap a broker, not define how acknowledgment, DLQ, or retry backoff work.

### What Was Reworked

| Standard | Before | After |
|----------|--------|-------|
| S1 (Queue Abstraction) | Pre-defined `MessageProducer`/`MessageConsumer` Protocols | Let Protocol shape emerge from wrapping SQS |
| S3 (Delivery Semantics) | App-level at-least-once standard | Managed service's responsibility |
| S4 (DLQ Policy) | App architecture concern | SQS/Terraform config concern |
| S5 (Consumer Lifecycle) | Prescriptive health checks, drain semantics | Essential lifecycle points only (start/stop/pluggy) |
| S6 (Queue Settings) | 5 settings keys | 2 keys: `QUEUE_BACKEND`, `QUEUE_ENDPOINT_URL` |

---

## 4. Interim Acceptance: Custom Code Justification

| Component | Why Custom Is Accepted (Interim) | Future Delegation Trigger |
|-----------|----------------------------------|--------------------------|
| Circuit breaker | Working, tested, proportional | When `pybreaker` Tier-5 ADR is authored |
| In-process retry | Working, tested; DynamoDB store has no library equivalent | When `tenacity` Tier-5 ADR is authored |
| Event dispatcher | ~300 LOC, simple pub/sub; library adds weight without benefit | If events need to cross ECS task boundaries → SNS/EventBridge |
| Idempotency | ~250 LOC, thin DynamoDB wrapper | If complexity grows → evaluate Lambda Powertools |
