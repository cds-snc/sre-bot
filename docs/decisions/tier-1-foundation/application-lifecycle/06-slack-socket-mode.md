# Slack Socket Mode

Start Slack Socket Mode client in daemon thread during initialization Phase 6.

---

## Implementation

```python
import threading
import structlog
from slack_bolt.adapter.socket_mode import SocketModeHandler

logger = structlog.get_logger()

def start_slack_socket_mode(app: FastAPI):
    """Start Slack Socket Mode in daemon thread."""
    log = logger.bind(phase="socket_mode")
    
    if not app.state.settings.slack.enabled:
        log.info("socket_mode_disabled")
        return
    
    log.info("socket_mode_starting")
    
    # Create Socket Mode handler
    socket_handler = SocketModeHandler(
        app_token=app.state.settings.slack.app_token,
        client=app.state.slack_client,
    )
    
    # Start in daemon thread (non-blocking)
    thread = threading.Thread(
        target=socket_handler.start,
        daemon=True,  # Daemon thread - exits with main process
        name="SlackSocketModeThread",
    )
    thread.start()
    
    app.state.socket_mode_handler = socket_handler
    log.info("socket_mode_started")
```

---

## Thread Behavior

- **Daemon Thread**: Exits automatically when main process terminates
- **Non-Blocking**: Does not block other initialization phases
- **Graceful Shutdown**: Socket Mode handler closes on SIGTERM

---

## Rules

- ✅ Run in daemon thread
- ✅ Do not block initialization
- ✅ Store handler in `app.state`
- ✅ Handle missing configuration gracefully
- ❌ Never run on main thread
- ❌ Never join the thread (would block)
