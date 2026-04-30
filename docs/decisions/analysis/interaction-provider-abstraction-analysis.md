# Interaction Provider Abstraction Analysis

**Date:** 2026-04-29  
**Related ADRs:** ADR-0025 (superseded), ADR-0059, ADR-0078  
**Purpose:** Decision rationale for rejecting the unified InteractionProvider Protocol

---

## Problem

The SRE Bot must support multiple collaboration platforms (Slack, Teams, potentially others) as optional interaction surfaces. ADR-0059 proposed a centralized `InteractionProvider` Protocol and `PlatformService` facade. This analysis challenges whether that abstraction is the right layer.

---

## 1. Operational Scenarios

| Scenario | Config | What Works | Architectural Implication |
|----------|--------|-----------|--------------------------|
| **A** No platform | `SLACK_ENABLED=false, TEAMS_ENABLED=false` | HTTP endpoints, background jobs | Features must be fully functional without any platform hookimpl running |
| **B** Slack only | `SLACK_ENABLED=true` | A + Slack commands/modals/actions | Each feature controls its own Slack surface |
| **C** Teams only | `TEAMS_ENABLED=true` | A + Teams handlers | Same pattern, different platform |
| **D** Multi-platform | Both enabled | Both transports active; features support what they've implemented | New concerns: message routing, identity mapping, state consistency |

---

## 2. Where the Unified Abstraction Leaks

Platform interactions are not symmetric. A unified Protocol either becomes lowest-common-denominator or leaky:

| Concern | Slack | Teams | HTTP |
|---------|-------|-------|------|
| Acknowledgment | Synchronous `ack()` within 3s | Turn-based implicit ack | Standard HTTP response |
| Views/modals | `trigger_id` → `views.open()` → submission event | Adaptive Card in conversation | N/A |
| Components | Block Kit JSON | Adaptive Cards JSON (different schema) | HTML/JSON |
| Threading | `thread_ts` | Reply chain | N/A |
| Rich text | `mrkdwn` format | Markdown subset + Adaptive Card elements | Standard Markdown/HTML |

A `register_command(name, handler: Callable[..., Any])` erases type information — Slack handlers receive `(ack, respond, command, say)` while Teams handlers receive `TurnContext`. The signatures are not equivalent. This defeats mypy enforcement (ADR-0077).

---

## 3. Authoritative Framework Alignment

| Source | Principle | Application |
|--------|-----------|-------------|
| **Hexagonal Architecture** (Cockburn) | Each external system gets its own adapter translating foreign → domestic vocabulary | `interactions/slack.py` and `interactions/http.py` are separate adapters into `ingress.py` |
| **Cosmic Python** (Percival & Gregory) | "A gateway translates a foreign vocabulary which would otherwise complicate the host code" | Multiple gateways (per platform) is correct when foreign vocabularies diverge |
| **Fowler's Gateway Pattern** | "A gateway is written by the client for its particular use" | Gateway shape should be determined by what the feature needs, not by the platform |
| **Feature Toggles** (Hodgson/Fowler) | Platform enablement is an Ops Toggle with Inversion of Decision | Features receive enabled/disabled state via hookspec injection, not by querying a toggle router |
| **DDD Anti-Corruption Layer** (Evans) | Each foreign bounded context gets its own ACL | Slack's context ≠ Teams' context → each needs its own ACL |

---

## 4. Abstraction Risks

| Risk | Severity | Description |
|------|----------|-------------|
| Premature abstraction | HIGH | Only Slack is implemented. Abstractions from one implementation tend to be wrong for the second. Rule of Three applies. |
| Forced indirection | MEDIUM-HIGH | `PlatformService` facade adds complexity without improving testability. Hookimpl pattern is simpler. |
| Handler signature erasure | HIGH | `Callable[..., Any]` loses type safety that ADR-0077 mandates |
| Capability matrix coupling | MEDIUM | Runtime capability queries add complexity for a decision already encoded in codebase structure |

---

## 5. Chosen Alternative: Feature-Owned Interaction

Instead of centralizing interaction in a Protocol-based facade, the architecture uses:

### Feature-owned interaction surface

```
packages/<feature>/
├── interactions/
│   ├── ingress.py     # Channel-agnostic admission logic
│   ├── http.py        # HTTP endpoints (always present)
│   ├── slack.py       # Slack handlers (if feature supports Slack)
│   └── teams.py       # Teams handlers (if feature supports Teams)
├── service.py         # Business logic (never imports from interactions/)
├── presenters.py      # Channel-specific response formatting
└── __init__.py        # Pluggy hookimpls
```

### Infrastructure owns transport, not interaction

Infrastructure provides platform transport connections, SDK wrappers, settings, and hookspecs. It does NOT provide a unified InteractionProvider Protocol, PlatformService facade, or capability matrix.

### Outbound messaging gets a narrow abstraction

The one area where a unified abstraction helps is outbound notifications ("send to a configured channel"). A narrow `NotificationChannel` Protocol covers this without attempting to unify incompatible interaction models.

### Platform enablement is a settings concern

Features never check "is Slack enabled?" — if the hookspec fires, Slack is enabled. If it doesn't, nothing happens. HTTP routes and jobs work regardless.

---

## Outcome

This analysis directly informed:

- **ADR-0059 revision:** Removed Standards 1–3 (InteractionProvider Protocol, Capability Matrix, PlatformService facade). Added Standards 4–6 for platform transport lifecycle and notification routing.
- **ADR-0078 creation:** Codified concrete per-platform services, feature-owned interaction, config-driven platform availability. Superseded ADR-0025.
