---
adr_id: ADR-0021
title: "Platform Integration Conventions (Redirect)"
status: Superseded
decision_type: Standard
tier: Tier-2
date_created: unknown
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0025
  - ADR-0026
  - ADR-0027
  - ADR-0028
related_records: []
related_packages: []
review_state: current
---
# Platform Integration Conventions (Redirect)

**Status**: ✅ ACTIVE (Redirect)  
**Note**: This document has been superseded by comprehensive platform provider decisions.

## Quick Navigation

All platform integration architecture decisions are now documented in the current ADR set:

1. **[ADR-0025: Interaction Providers Concept](../0025-platform-providers-concept.md)** - Why we replaced command providers with platform providers (multi-feature abstraction)

2. **[ADR-0026: Explicit Registration Pattern](../0026-explicit-registration-pattern.md)** - Why we use explicit registration via Pluggy hooks instead of import-time auto-discovery

3. **[ADR-0027: Pluggy Plugin System Integration](../0027-pluggy-plugin-system.md)** - How we use Pluggy (pytest's plugin system) for registration and discovery

4. **[ADR-0028: Feature Interaction Layer Isolation](../0028-platform-feature-isolation.md)** - How packages organize platform-specific code in dedicated interaction layers

5. **[Platform ADR README](../../tier-2-infrastructure/platforms/README.md)** - Overview with quick reference, reading order, and FAQ

## Core Principles (Summary)

- ✅ **FastAPI-First**: All business logic exposed as HTTP endpoints; platform adapters wrap these endpoints
- ✅ **Platform Providers**: Multi-feature abstraction supporting commands, views, actions, messaging
- ✅ **Explicit Registration**: Pluggy hooks for type-safe, testable registration
- ✅ **Self-Contained Packages**: Each `/packages/<feature>/` is independently deployable
- ✅ **Platform Isolation**: Platform-specific code isolated in `platforms/` subdirectory

## For Quick Answers

- **"What changed from command providers?"** → [ADR-0025: Interaction Providers Concept](../0025-platform-providers-concept.md)
- **"Why explicit registration?"** → [ADR-0026: Explicit Registration Pattern](../0026-explicit-registration-pattern.md)
- **"How do I register a feature?"** → [ADR-0027: Pluggy Plugin System Integration](../0027-pluggy-plugin-system.md)
- **"How should I structure my package?"** → [ADR-0028: Feature Interaction Layer Isolation](../0028-platform-feature-isolation.md)