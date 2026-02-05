# Application Initialization Lifecycle

High-level initialization for FastAPI application using lifespan context manager.

See [application-lifecycle/](./application-lifecycle/) subdirectory for detailed specifications.

---

## Current Implementation

[main.py](/workspace/app/main.py) uses `app.add_event_handler("startup", ...)` for initialization.

---

## 7-Phase Initialization Sequence

1. **Configuration**: Load Settings singleton, configure logging
2. **Infrastructure**: Initialize core services, plugin managers
3. **Providers**: Discover and activate (Groups, Commands, Platforms)
4. **Features**: Register event handlers, platform plugins
5. **Commands**: Register commands with platforms
6. **Socket Mode**: Start Slack WebSocket (daemon thread, non-blocking)
7. **Background**: Scheduled jobs (production only)

---

## Key Principles

- ✅ Single Settings instance via `@lru_cache`
- ✅ Sequential phase execution
- ✅ Fail fast on critical errors
- ✅ Immutable registries after startup
- ✅ Structured logging per phase
- ✅ Graceful shutdown in reverse order

---

## Anti-patterns

- ❌ New initialization logic added via `app.add_event_handler("startup", ...)`
- ❌ Skipping or reordering phases
- ❌ Registering providers after startup

---

## Detailed Specifications

- [01-fastapi-lifespan-pattern.md](./application-lifecycle/01-fastapi-lifespan-pattern.md) - FastAPI lifespan context manager
- [02-settings-singleton.md](./application-lifecycle/02-settings-singleton.md) - Configuration singleton
- [03-initialization-phases.md](./application-lifecycle/03-initialization-phases.md) - 7-phase sequence
- [04-provider-discovery.md](./application-lifecycle/04-provider-discovery.md) - Provider activation
- [05-plugin-managers.md](./application-lifecycle/05-plugin-managers.md) - Plugin system
- [06-slack-socket-mode.md](./application-lifecycle/06-slack-socket-mode.md) - Slack integration startup
- [07-background-services.md](./application-lifecycle/07-background-services.md) - Scheduled jobs
- [08-graceful-shutdown.md](./application-lifecycle/08-graceful-shutdown.md) - Cleanup and shutdown
