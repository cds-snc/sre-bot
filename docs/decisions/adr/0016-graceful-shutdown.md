---
adr_id: ADR-0016
title: "Graceful Shutdown"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0005
  - ADR-0009
  - ADR-0011
  - ADR-0015
related_packages: []
review_state: stale
---
# Graceful Shutdown

## Context

When a SIGTERM signal arrives (ECS task stop), in-flight requests and background jobs must complete or be interrupted cleanly. We need a reverse shutdown sequence that mirrors startup.

## Decision

During lifespan shutdown (code after `yield`), execute shutdown phases in reverse order of startup. After all connections close and background work completes, the process exits cleanly.

## Consequences

- ✅ Clean resource release
- ✅ In-flight requests complete before exit
- ✅ Daemon threads and background jobs shut down properly
- ⚠️ Shutdown timeout must account for max in-flight request duration

---

Cleanup resources in reverse initialization order during lifespan shutdown.

---

## Implementation

```python
import structlog

logger = structlog.get_logger()

async def shutdown_services(app: FastAPI):
    """Graceful shutdown - reverse initialization order."""
    log = logger.bind(phase="shutdown")
    
    try:
        # Phase 7 Reverse: Stop background jobs
        if hasattr(app.state, "scheduler"):
            log.info("stopping_background_services")
            app.state.scheduler.shutdown(wait=True)
        
        # Phase 6 Reverse: Close Socket Mode
        if hasattr(app.state, "socket_mode_handler"):
            log.info("stopping_socket_mode")
            app.state.socket_mode_handler.close()
        
        # Phase 5 Reverse: Unregister commands (if needed)
        log.info("unregistering_commands")
        
        # Phase 4 Reverse: Unregister plugin handlers
        if hasattr(app.state, "plugin_manager"):
            log.info("stopping_plugins")
            app.state.plugin_manager.unregister()
        
        # Phase 3 Reverse: Close providers
        if hasattr(app.state, "providers"):
            log.info("closing_providers")
            for provider in app.state.providers.get("platforms", []):
                if hasattr(provider, "close"):
                    await provider.close()
        
        # Phase 2 Reverse: Close infrastructure services
        log.info("closing_infrastructure")
        
        # Phase 1 Reverse: Settings cleanup (none needed)
        log.info("shutdown_complete")
    
    except Exception as e:
        log.error("shutdown_error", error=str(e))
```

---

## Rules

- ✅ Reverse initialization order
- ✅ Clean up all resources
- ✅ Log shutdown progress
- ✅ Handle missing state gracefully
- ✅ Wait for threads to finish
- ❌ Never raise exceptions during shutdown
- ❌ Never block indefinitely
