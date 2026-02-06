# Background Services

Initialize scheduled background jobs during initialization Phase 7 (production only).

---

## Implementation

```python
import structlog
from apscheduler.schedulers.background import BackgroundScheduler

logger = structlog.get_logger()

def initialize_background_services(app: FastAPI):
    """Initialize background task scheduler."""
    log = logger.bind(phase="background")
    
    if app.state.settings.environment == "development":
        log.info("background_services_skipped", reason="development_mode")
        return
    
    log.info("background_services_initializing")
    
    # Create scheduler
    scheduler = BackgroundScheduler(daemon=True)
    
    # Register jobs
    scheduler.add_job(
        func=sync_groups_job,
        trigger="interval",
        hours=1,
        args=(app.state.settings,),
        name="sync_groups",
    )
    
    scheduler.add_job(
        func=cleanup_audit_trail_job,
        trigger="interval",
        hours=6,
        args=(app.state.settings,),
        name="cleanup_audit_trail",
    )
    
    # Start scheduler
    scheduler.start()
    app.state.scheduler = scheduler
    
    log.info("background_services_ready", jobs=scheduler.get_jobs())

def sync_groups_job(settings):
    log = logger.bind(job="sync_groups")
    log.info("job_started")
    # Sync groups...
    log.info("job_completed")
```

---

## Rules

- ✅ Use APScheduler for job scheduling
- ✅ Run only in production environment
- ✅ Use daemon threads
- ✅ Log job start/completion
- ❌ Never run jobs in development
- ❌ Never block on job execution
