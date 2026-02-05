# Application Initialization Pattern

**Reference**: `docs/decisions/tier-1-foundation/application-lifecycle/`

## Pattern

Use FastAPI `lifespan` context manager. No `add_event_handler("startup")` calls.

---

## Lifespan Pattern

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # STARTUP - before yield
    settings = initialize_configuration()
    initialize_infrastructure(settings)
    initialize_providers(settings)
    
    app.state.settings = settings
    
    yield  # Application accepts requests
    
    # SHUTDOWN - after yield
    await shutdown_services(app)

app = FastAPI(lifespan=lifespan)
```

**Pattern**: All init before `yield`, all cleanup after `yield`.

---

## Initialization Phases

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 1: Configuration
    settings = initialize_configuration()
    
    # Phase 2: Infrastructure
    initialize_infrastructure(settings)
    
    # Phase 3: Providers (Groups → Commands → Platforms)
    providers = initialize_providers(settings)
    app.state.providers = providers
    
    # Phase 4-5: Features and Commands
    initialize_features(app, settings)
    register_platform_commands(app, settings)
    
    # Phase 6: Socket Mode (daemon thread)
    start_slack_socket_mode(app)
    
    # Phase 7: Background (production only)
    initialize_background_services(app)
    
    yield
    
    # Shutdown (reverse order)
    stop_slack_socket_mode(app)
    await shutdown_services(app)
```

**Pattern**: Sequential phases with explicit dependencies.

---

## Socket Mode Pattern

```python
import threading

def start_slack_socket_mode(app: FastAPI) -> None:
    """Start Socket Mode in daemon thread."""
    if not hasattr(app.state, "slack_bot"):
        return
    
    handler = SocketModeHandler(
        app=app.state.slack_bot,
        app_token=app.state.slack_app_token,
    )
    
    def run_socket_mode():
        handler.connect()  # Blocks forever
    
    thread = threading.Thread(
        target=run_socket_mode,
        daemon=True,  # Dies with main process
        name="slack-socket-mode"
    )
    thread.start()
    
    app.state.socket_mode_handler = handler
```

**Pattern**: Daemon thread for blocking `handler.connect()`.

---

## Shutdown Pattern

```python
async def shutdown_services(app: FastAPI) -> None:
    """Shutdown in reverse initialization order."""
    log = logger.bind(phase="shutdown")
    
    # 1. Stop scheduled tasks
    if hasattr(app.state, "task_executor"):
        app.state.task_executor.shutdown(wait=True)
    
    # 2. Shutdown event dispatcher
    shutdown_event_executor()
    
    # 3. Close clients
    if hasattr(app.state, "aws_clients"):
        app.state.aws_clients.close_all()
    
    # 4. Flush logs
    import logging
    logging.shutdown()
```

**Pattern**: Reverse order, continue on errors, log all steps.

---

## Forbidden Patterns

```python
# ❌ add_event_handler
app.add_event_handler("startup", startup_func)  # WRONG

# ❌ @app.on_event decorator
@app.on_event("startup")  # WRONG
async def startup():
    pass

# ❌ Socket Mode without thread
handler.connect()  # WRONG - blocks forever
yield  # Never reached

# ❌ Shutdown before Socket Mode
await shutdown_services(app)  # WRONG - do this last
stop_slack_socket_mode(app)  # Should be first

# ❌ Non-daemon thread
threading.Thread(target=run, daemon=False)  # WRONG
```

---

## Pre-Implementation Checklist

Before modifying initialization:

1. ☐ Using `@asynccontextmanager` lifespan
2. ☐ No `add_event_handler()` calls
3. ☐ All startup before `yield`
4. ☐ All shutdown after `yield`
5. ☐ Socket Mode in daemon thread
6. ☐ Shutdown in reverse initialization order
7. ☐ State stored in `app.state`
