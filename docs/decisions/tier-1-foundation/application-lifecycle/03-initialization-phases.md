# Initialization Phases

Execute initialization in 7 sequential phases during FastAPI lifespan startup.

---

## Phase Order

```python
# app/main.py - lifespan function
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Execute phases in strict order."""
    log = logger.bind(phase="initialization")
    
    # Phase 1: Configuration
    settings = initialize_configuration()
    
    # Phase 2: Infrastructure
    initialize_infrastructure(settings)
    
    # Phase 3: Providers
    providers = initialize_providers(settings)
    
    # Phase 4: Features
    initialize_features(app, settings)
    
    # Phase 5: Commands
    register_platform_commands(app, settings)
    
    # Phase 6: Socket Mode
    start_slack_socket_mode(app)
    
    # Phase 7: Background
    initialize_background_services(app)
    
    log.info("all_phases_complete")
    yield  # Ready for requests
    
    # Shutdown: Reverse order
    await shutdown_services(app)
```

---

## Phase Details

### Phase 1: Configuration

Load environment variables, validate, configure logging.

```python
import structlog
from infrastructure.services import get_settings

logger = structlog.get_logger()

def initialize_configuration() -> Settings:
    settings = get_settings()  # Singleton - loads once
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
    )
    log = logger.bind(phase="configuration")
    log.info("configuration_loaded")
    return settings
```

### Phase 2: Infrastructure

Initialize DynamoDB, idempotency cache, plugin managers.

```python
def initialize_infrastructure(settings: Settings) -> None:
    log = logger.bind(phase="infrastructure")
    log.info("infrastructure_initializing")
    # Create service instances...
    log.info("infrastructure_ready")
```

### Phase 3: Providers

Discover and activate (Groups, Commands, Platforms).

```python
def initialize_providers(settings: Settings) -> dict:
    log = logger.bind(phase="providers")
    log.info("providers_initializing")
    providers = {"groups": [], "commands": [], "platforms": []}
    # Register providers...
    log.info("providers_ready", count=len(providers))
    return providers
```

### Phase 4: Features

Register event handlers and platform plugins.

```python
def initialize_features(app: FastAPI, settings: Settings) -> None:
    log = logger.bind(phase="features")
    log.info("features_initializing")
    # Register handlers...
    log.info("features_ready")
```

### Phase 5: Commands

Register commands with platforms.

```python
def register_platform_commands(app: FastAPI, settings: Settings) -> None:
    log = logger.bind(phase="commands")
    log.info("commands_registering")
    # Register commands...
    log.info("commands_registered")
```

### Phase 6: Socket Mode

Start Slack WebSocket (non-blocking daemon thread).

```python
def start_slack_socket_mode(app: FastAPI) -> None:
    log = logger.bind(phase="socket_mode")
    log.info("socket_mode_starting")
    # Start daemon thread for Slack...
    log.info("socket_mode_started")
```

### Phase 7: Background

Schedule background jobs (production only).

```python
def initialize_background_services(app: FastAPI) -> None:
    log = logger.bind(phase="background")
    log.info("background_services_starting")
    # Schedule jobs...
    log.info("background_services_ready")
```

---

## Rules

- ✅ Sequential execution
- ✅ Fail fast on error
- ✅ Log each phase
- ✅ Store state in `app.state`
- ❌ Never skip phases
- ❌ Never reverse order during startup
