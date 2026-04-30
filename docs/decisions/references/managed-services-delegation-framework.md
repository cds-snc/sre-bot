# Managed Services Delegation Framework

**Date:** 2026-04-30  
**Related ADRs:** ADR-0045 P7, ADR-0047 P6, ADR-0054, ADR-0055, ADR-0056, ADR-0077

---

## Purpose

This document defines the three-tier delegation hierarchy that governs how infrastructure concerns are served. ADR-0045 P7 codifies the principle; this reference provides the full framework, authoritative guidance alignment, configurable backend model, and library governance criteria.

---

## 1. The Three-Tier Hierarchy

Every infrastructure concern must be served by the highest applicable tier:

| Tier | Description | Examples | App Code | Ops Burden |
|------|-------------|----------|----------|------------|
| **1 — Managed Cloud Service** (preferred) | Cloud provider handles availability, scaling, patching | SQS, DynamoDB, SNS, EventBridge, S3 | Thin SDK wrapper (~50–150 LOC) | Minimal |
| **2 — Industry Library** (fallback) | Proven library handles core logic; app wraps it | `tenacity`, `pybreaker`, `schedule`, `slowapi`, `structlog` | Thin adapter (~30–100 LOC) | Library upgrades |
| **3 — Custom Implementation** (last resort) | No managed service or library covers the need | Event dispatcher, idempotency cache | Proportional scope, flagged for future delegation | Full ownership |

### Decision Flow

1. Can a managed cloud service handle this? → **Tier 1.** Wrap SDK, define Protocol (ADR-0077 Category A), configure via settings, provide in-memory dev fallback.
2. Does a proven library handle this? → **Tier 2.** Wrap library in thin adapter. Protocol optional (Category B).
3. Neither applies? → **Tier 3.** Justify why, keep scope minimal, flag for future delegation.

---

## 2. Authoritative Guidance Alignment

The hierarchy converges established architectural principles:

| Source | Key Guidance | Alignment |
|--------|-------------|-----------|
| **Twelve-Factor IV** (Backing Services) | App treats all backing services identically; swap happens in config, not code | Supports configurable backend model |
| **AWS Well-Architected** (Operational Excellence) | "Use managed services. Reduce undifferentiated heavy lifting." | Managed services are the default |
| **Azure Architecture Guide** | "Use PaaS instead of IaaS. Look for places to incorporate PaaS for caches, queues, storage." | PaaS preferred even when some custom infra is needed |
| **GC Cloud Adoption Strategy** (Principle 8) | "Consider portability and interoperability." Priority: SaaS > PaaS > IaaS | Cloud portability is policy, not just good practice. Maps to Tier 1 > Tier 2 > Tier 3 |
| **Hexagonal Architecture** (Cockburn) | Port = interface (Protocol); Adapter = implementation behind it | P7 governs what sits behind the adapter; P6 governs the port shape |
| **Azure Cloud Design Patterns** | Circuit Breaker, Retry, Queue-Based Load Leveling all assume managed backing services | App applies patterns via libraries/services, not by reimplementing them |

---

## 3. Configurable Backend Model

### Requirement

Given GC portability policy and the need for AWS primary / Azure hedge / local dev, every infrastructure service must be backend-configurable via settings.

### Pattern: Protocol + Settings-Driven Provider

```python
# Protocol (the Port)
class QueueService(Protocol):
    async def send(self, queue: str, message: MessageEnvelope) -> OperationResult[None]: ...
    async def receive(self, queue: str, max: int) -> OperationResult[list[MessageEnvelope]]: ...

# Settings
class QueueSettings(BaseSettings):
    QUEUE_BACKEND: Literal["memory", "sqs", "azure_servicebus"] = "memory"

# Provider (composition root)
@lru_cache(maxsize=1)
def get_queue_service() -> QueueService:
    settings = get_queue_settings()
    match settings.QUEUE_BACKEND:
        case "sqs":       return SQSQueueService(settings)
        case "memory":    return InMemoryQueueService()
```

### Backend Classification

| Concern | Current | Target Backends | Settings Key |
|---------|---------|----------------|-------------|
| Storage/DB | DynamoDB | DynamoDB, RDS, CosmosDB | `STORAGE_BACKEND` |
| Queue | None | SQS, Service Bus, in-memory | `QUEUE_BACKEND` |
| Retry store | DynamoDB + in-memory | DynamoDB, SQS DLQ, in-memory | `RETRY_BACKEND` |
| Events | ThreadPoolExecutor | SNS/EventBridge, in-process | `EVENT_BACKEND` |
| Scheduled jobs | `schedule` library | `schedule`, CloudWatch Events | `SCHEDULER_BACKEND` |
| Notifications | GC Notify | GC Notify, SES, Azure Comms | `NOTIFICATION_BACKEND` |
| Locking | DynamoDB conditional writes | DynamoDB, Redis | `LOCK_BACKEND` |

### Dev/Test Fallback Requirement

Every Protocol-backed service must have an in-memory or local fallback (ADR-0054). Fallbacks satisfy the Protocol contract sufficiently for feature development and unit testing. Integration tests against real services run in a separate CI stage.

---

## 4. Library Selection Governance

Library selections for infrastructure concerns (Tier 2) require a Tier-5 ADR (ADR-0044, ADR-0051).

### Evaluation Criteria

| Criterion | Threshold |
|-----------|-----------|
| Maturity | >3 years active, >1000 GitHub stars |
| Maintenance | Maintainer response within 90 days; release within last 12 months |
| License | MIT, BSD, Apache 2.0, or compatible |
| Dependencies | Minimal transitive deps; no C extensions unless justified |
| Python version | 3.12+ |
| Type hints | `py.typed` marker or >80% coverage |
| Async support | Native async API or thread-safe sync API |
| Testing | Provides test utilities/fakes or is easily mockable |

### Current Custom Code vs. Library Candidates

| Component | Custom LOC | Library Candidate | Status |
|-----------|-----------|-------------------|--------|
| Circuit breaker | ~300 | `pybreaker` | Tier-5 ADR needed |
| In-process retry | ~400 | `tenacity` | Tier-5 ADR needed |
| Event dispatcher | ~300 | Keep — proportional, simple | No change |
| Idempotency | ~250 | Keep — evaluate later | No change |

---

## 5. The Guiding Question

For every infrastructure concern:

> "Is the application providing an abstraction layer over a capability, or is it _being_ the capability?"

- Wrapping DynamoDB for storage → abstraction layer
- Wrapping `schedule` for jobs → abstraction layer
- Building a 3-state circuit breaker → being the capability (delegate to `pybreaker`)
- Defining custom message acknowledgment Protocols → being the capability (delegate to SQS)
