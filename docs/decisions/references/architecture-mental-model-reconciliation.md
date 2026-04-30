# Architecture Mental Model Reconciliation: Backstage vs Python/FastAPI

**Date:** 2026-04-29  
**Related ADRs:** ADR-0045 P3/P6, ADR-0048 B5/B7, ADR-0076, ADR-0077

---

## Problem

The `app/infrastructure` layer was designed using Backstage (Spotify) as a mental model for shared core services. However, Backstage is a Node.js/TypeScript application with a fundamentally different service architecture. This mismatch produced:

1. A blanket sibling isolation rule (ADR-0048 B5) borrowed from Backstage's *plugin* isolation — but applied to the *service* layer (the opposite of what Backstage does).
2. Missing Protocol contracts for most infrastructure services.
3. No explicit ADR articulating the infrastructure layer's role as a shared, swappable service platform.

ADR-0076 surfaced the B5 problem empirically (61% violation rate). This document traces the root cause.

---

## What Backstage Actually Does

Backstage distinguishes two levels sharply:

| Concept | Backstage Term | Isolation | Communication |
|---------|---------------|-----------|---------------|
| **Core services** | Backend Services | Shared — **freely depend on each other** via declared `deps` | In-process DI |
| **Business features** | Backend Plugins | Fully isolated — **never communicate through code** | Network only |

Services declare `deps: { logger, database, ... }` and compose freely. A `ServiceFactory` is the constructor; the backend instance is the DI container. Services can be plugin-scoped or root-scoped (singleton).

---

## What Was Borrowed Correctly

| Backstage Concept | sre-bot Equivalent |
|-------------------|--------------------|
| Core services as shared utility layer | `app/infrastructure/` |
| Service factories with DI | `providers.py` with `@lru_cache` |
| Single DI container | `providers.py` as composition root |
| Plugin-based feature discovery | `pluggy` + `auto_discover_plugins` |
| Feature packages as autonomous units | `app/packages/` |
| Extension points for registration | `hookspecs/features.py` |

## What Was Misapplied

| Backstage Rule | Where It Applies | How It Was Misapplied | Impact |
|---------------|-----------------|----------------------|--------|
| "Plugins must never communicate through code" | Between **plugins** (features) | Applied as ADR-0048 B5 to **infrastructure services** | 61% violation rate |
| Implicit swappability via TypeScript interfaces | Service interfaces mandatory | No Protocol requirement for Python services | Most services concrete, no swap path |

### The Core Misunderstanding

Backstage's plugin isolation rule was applied to the wrong architectural layer:

```
Backstage (correct):
  Services ←→ freely compose          Plugins ←→ isolated (network-only)

sre-bot (as designed by B5 — wrong):
  Infrastructure ←→ blanket import ban   Packages ←→ isolated

sre-bot (corrected):
  Infrastructure ←→ compose freely in composition root
  Packages ←→ consume via Protocol contracts only
```

---

## Correct Architectural Analogies

| sre-bot Layer | Correct Analogy | NOT This |
|---------------|-----------------|----------|
| `app/infrastructure/` | Backstage **core services**; Django **contrib**; Flask **extensions** | Backstage **plugins** |
| `app/packages/` | Backstage **plugins**; Django **apps** | Backstage **services** |
| `providers.py` | Backstage's `createBackend()` DI container | A mere helper file |
| `app/infrastructure/clients/` | Backstage's default service factory implementations | Services themselves |

---

## Corrections Applied

These findings led to three ADR changes:

1. **ADR-0045 P6 added** (Protocol-Driven Service Contracts) — captures the core intent that was present in design but never codified. Python/FastAPI equivalent of Backstage's ServiceRef + ServiceFactory.
2. **ADR-0048 B5 renamed** from "Infrastructure Sibling Isolation" to "Infrastructure Composition Governance" — reflects correct mental model.
3. **ADR-0076 created** (Infrastructure Intra-Layer Import Standard) — evidence-based three-part standard replacing the blanket ban with composition-root governance, shared value-type access, and client encapsulation.

---

## Protocol Contract Gap (at time of analysis)

| Service | Protocol? | Gap |
|---------|----------|-----|
| DirectoryProvider | Yes | None |
| RetryStore / RetryProcessor | Yes | None |
| ResponseChannel | Yes | None |
| BackgroundJobRegistry | Yes | None |
| StorageService | **No** | Critical — storage-agnostic goal unmet |
| IdentityService | **No** | Medium — could have multiple backends |
| AuditTrailService | **No** | Medium |
| NotificationService | **No** | Low |
| EventDispatcher | **No** | Low |

5 of 14 feature-facing services had Protocol contracts. ADR-0077 now governs the migration path (Category A services require Protocol + P1 migration).
