# Platform Integration Conventions (Redirect)

**Status**: ✅ ACTIVE (Redirect)  
**Note**: This document has been superseded by comprehensive platform provider decisions.

## Quick Navigation

All platform integration architecture decisions are now documented in the [platforms/](./platforms/) subdirectory:

1. **[01-platform-providers-concept.md](./platforms/01-platform-providers-concept.md)** - Why we replaced command providers with platform providers (multi-feature abstraction)

2. **[02-explicit-registration-pattern.md](./platforms/02-explicit-registration-pattern.md)** - Why we use explicit registration via Pluggy hooks instead of import-time auto-discovery

3. **[03-pluggy-plugin-system.md](./platforms/03-pluggy-plugin-system.md)** - How we use Pluggy (pytest's plugin system) for registration and discovery

4. **[04-platform-feature-isolation.md](./platforms/04-platform-feature-isolation.md)** - How packages organize platform-specific code in `/packages/<feature>/platforms/` subdirectory

5. **[README.md](./platforms/README.md)** - Overview with quick reference, reading order, and FAQ

## Core Principles (Summary)

- ✅ **FastAPI-First**: All business logic exposed as HTTP endpoints; platform adapters wrap these endpoints
- ✅ **Platform Providers**: Multi-feature abstraction supporting commands, views, actions, messaging
- ✅ **Explicit Registration**: Pluggy hooks for type-safe, testable registration
- ✅ **Self-Contained Packages**: Each `/packages/<feature>/` is independently deployable
- ✅ **Platform Isolation**: Platform-specific code isolated in `platforms/` subdirectory

## For Quick Answers

- **"What changed from command providers?"** → [01-platform-providers-concept.md](./platforms/01-platform-providers-concept.md)
- **"Why explicit registration?"** → [02-explicit-registration-pattern.md](./platforms/02-explicit-registration-pattern.md)
- **"How do I register a feature?"** → [03-pluggy-plugin-system.md](./platforms/03-pluggy-plugin-system.md)
- **"How should I structure my package?"** → [04-platform-feature-isolation.md](./platforms/04-platform-feature-isolation.md)