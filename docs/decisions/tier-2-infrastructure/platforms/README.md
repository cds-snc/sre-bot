# Platform Provider Architecture Decisions

This directory contains architectural decisions related to platform provider integration, registration patterns, and feature isolation for collaboration platforms (Slack, Microsoft Teams, Discord).

---

## Overview

As part of our large release, we **replaced the command provider concept** with a more comprehensive **platform providers architecture** that supports rich interactive features beyond simple commands (views, modals, interactive cards, messaging, etc.).

These ADRs document the key decisions that enable:
- ✅ Multi-platform support (Slack, Teams, Discord, HTTP API)
- ✅ Self-contained feature packages in `/packages/`
- ✅ Type-safe plugin registration via Pluggy
- ✅ Platform-agnostic business logic
- ✅ Simplified `main.py` application startup

---

## Reading Order

We recommend reading these ADRs in order:

### 1. [Platform Providers Concept](./01-platform-providers-concept.md)
**What changed**: Replaced narrow "command providers" with comprehensive "platform providers"

**Key decision**: Platform providers model the full feature set of collaboration platforms (commands, views, cards, messaging, files), not just text commands.

**Read this if**: You want to understand why we moved beyond command-only abstractions.

---

### 2. [Explicit Registration Pattern](./02-explicit-registration-pattern.md)
**What changed**: Adopted Pluggy hooks instead of import-time auto-discovery

**Key decision**: Use explicit invocation of registration (`discover_and_register_platforms()`) with Pluggy's hook-based discovery of implementations.

**Read this if**: You want to understand why we rejected import-time registration and chose Pluggy.

---

### 3. [Pluggy Plugin System](./03-pluggy-plugin-system.md)
**What changed**: Integrated pytest's Pluggy plugin framework into our infrastructure

**Key decision**: Use battle-tested Pluggy (1400+ pytest plugins) instead of building custom registry system.

**Read this if**: You want to understand how to create hook specifications, plugin managers, and feature implementations.

---

### 4. [Platform Feature Isolation](./04-platform-feature-isolation.md)
**What changed**: Standardized package structure with dedicated `platforms/` subdirectory

**Key decision**: Features in `/packages/` follow a consistent structure that isolates platform-specific code from business logic.

**Read this if**: You want to understand how to structure a feature package with platform integrations.

---

## Quick Reference

### For Feature Developers

**Goal**: Add a new feature with Slack and Teams support

**Steps**:
1. Create package structure (see [ADR 04](./04-platform-feature-isolation.md))
2. Implement HTTP endpoints in `routes.py` (platform-agnostic)
3. Implement business logic in `service.py`
4. Create platform adapters in `platforms/slack.py`, `platforms/teams.py`
5. Add Pluggy hooks in `__init__.py` (see [ADR 03](./03-pluggy-plugin-system.md))

**Template**:
```
packages/myfeature/
├── __init__.py              # @hookimpl decorators
├── routes.py                # POST /myfeature/action
├── service.py               # action(request) -> OperationResult
└── platforms/
    ├── slack.py             # /myfeature → POST /myfeature/action → Block Kit
    └── teams.py             # @bot myfeature → POST /myfeature/action → Adaptive Card
```

---

### For Platform Developers

**Goal**: Add support for a new platform (e.g., Discord)

**Steps**:
1. Create provider in `infrastructure/platforms/providers/discord.py` (see [ADR 01](./01-platform-providers-concept.md))
2. Define hook spec in `infrastructure/hookspecs/platforms.py` (see [ADR 03](./03-pluggy-plugin-system.md))
3. Update plugin manager in `infrastructure/services/plugins/platforms.py`
4. Export provider accessor in `infrastructure/platforms/__init__.py`
5. Update feature packages to implement Discord hooks

---

### For Infrastructure Developers

**Goal**: Create a new extensible core service (e.g., event handlers)

**Steps**:
1. Define hook spec in `infrastructure/hookspecs/<service>.py`
2. Create plugin manager in `infrastructure/services/plugins/<service>.py`
3. Export via `infrastructure/services/__init__.py`
4. Document in architecture docs

**Pattern**: See "Generic Pattern for Extensible Services" in [ADR 03](./03-pluggy-plugin-system.md)

---

## Key Principles

### 1. FastAPI-First
✅ All business logic exposed as HTTP endpoints  
✅ Platform adapters call HTTP endpoints internally  
✅ No platform-specific code in business logic  

### 2. Explicit Registration
✅ Registration invoked explicitly: `discover_and_register_platforms()`  
✅ Hook implementations discovered via Pluggy  
✅ No import-time side effects  

### 3. Self-Contained Packages
✅ Each package in `/packages/` is complete vertical slice  
✅ Platform code isolated in `platforms/` subdirectory  
✅ Pluggy hooks in `__init__.py`  

### 4. Configuration-Driven
✅ Platforms enabled via environment variables  
✅ Providers passed explicitly to registration  
✅ No magic discovery of enabled platforms  

---

## Related Documentation

### Architecture Documents
- [Platform-Centric Collaboration Architecture](../../../architecture-review/PLATFORM_CENTRIC_ARCHITECTURE.md) - Comprehensive architecture guide
- [Pluggy Integration Design](../../../architecture/PLUGGY_INTEGRATION_DESIGN.md) - Detailed Pluggy implementation patterns
- [Platform Providers Validation](../../../architecture-review/PLATFORM_PROVIDERS_VALIDATION.md) - Validation against Python best practices

### Assessment Documents
- [Platform Providers Architecture Assessment](../../../architecture-review/PLATFORM_PROVIDERS_ARCHITECTURE_ASSESSMENT.md) - Analysis leading to Pluggy decision
- [Explicit Registration Decision](../../../architecture-review/EXPLICIT_REGISTRATION_DECISION.md) - Registration pattern decision rationale

### Parent ADRs
- [04-command-framework-platform-abstraction.md](../04-command-framework-platform-abstraction.md) - Core platform integration conventions

---

## Migration Status

### Current State (February 2026)
- ✅ Platform provider infrastructure implemented
- ✅ Pluggy integration complete
- ✅ Explicit registration pattern active
- 🔄 Feature packages migrating from `/modules/` to `/packages/`

### Migration Path
- **New features**: Use `/packages/` structure (mandatory)
- **Existing features**: Migrate opportunistically when making changes
- **Coexistence**: `/modules/` and `/packages/` coexist during transition

See [ADR 04](./04-platform-feature-isolation.md) for detailed migration strategy.

---

## Questions?

- **"How do I register a new command?"** → See [ADR 03: Pluggy Plugin System](./03-pluggy-plugin-system.md)
- **"Why can't I use import-time registration?"** → See [ADR 02: Explicit Registration Pattern](./02-explicit-registration-pattern.md)
- **"What's the difference between platform providers and command providers?"** → See [ADR 01: Platform Providers Concept](./01-platform-providers-concept.md)
- **"How should I structure my package?"** → See [ADR 04: Platform Feature Isolation](./04-platform-feature-isolation.md)
- **"Where's the implementation guide?"** → See [Platform-Centric Collaboration Architecture](../../../architecture-review/PLATFORM_CENTRIC_ARCHITECTURE.md)

---

## Revision History

- **2026-02-05**: Initial platform ADRs created (ADR 01-04)
