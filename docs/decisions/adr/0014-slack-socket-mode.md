---
adr_id: ADR-0014
title: "Slack Socket Mode"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by: []
related_records:
  - ADR-0011
  - ADR-0015
related_packages: []
review_state: stale
---
# Slack Socket Mode

## Context

Slack webhooks require public HTTPS endpoints; some environments may not support this. Socket Mode allows Slack to initiate WebSocket connections from within the private network, eliminating egress requirements.

## Decision

Implement Slack Socket Mode as Phase 6 startup. Use a daemon thread (non-blocking) to maintain the WebSocket connection. Store the handler in `app.state` for graceful shutdown reference.

## Consequences

- ✅ Works in private networks without egress
- ✅ Non-blocking daemon thread doesn't delay HTTP startup
- ⚠️ Requires Slack Socket Mode token configuration
- ⚠️ Daemon thread lifecycle must be managed during shutdown

---

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
