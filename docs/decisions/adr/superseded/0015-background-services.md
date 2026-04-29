---
adr_id: ADR-0015
title: "Background Services"
status: Superseded
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0058
related_records:
  - ADR-0011
  - ADR-0016
related_packages: []
review_state: superseded
---
# Background Services

## Context

Scheduled jobs (e.g., periodic syncs) are production-only concerns. We need a non-blocking task scheduler that integrates cleanly with the lifespan pattern and shuts down gracefully.

## Decision

Use AsyncIOScheduler (preferred) or BackgroundScheduler during Phase 7 startup. Schedule only in production environments (conditional on environment variable). Store scheduler in `app.state` for shutdown reference.

## Consequences

- ✅ Non-blocking scheduler per ECS task
- ✅ Clean integration with lifespan startup/shutdown
- ✅ Async-native job execution
- ⚠️ Jobs must handle task horizontal scaling (multiple tasks running same job)

---

Initialize scheduled background jobs during initialization Phase 7 (production only).

---

## Scheduler Selection

Choose based on job characteristics:

- **`BackgroundScheduler`** — Sync jobs (CPU-bound, legacy code). Runs in separate daemon thread pool. Each job uses one thread.
- **`AsyncIOScheduler`** — Async jobs (I/O-bound: database, HTTP, file operations). Runs on the FastAPI event loop. Preferred for new jobs. Jobs don't consume thread pool slots.

---

## Implementation

### Option 1: Async jobs (Recommended for I/O-bound work)

```python
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

logger = structlog.get_logger()

def initialize_background_services(app: FastAPI):
    """Initialize async background task scheduler."""
    log = logger.bind(phase="background")
    
    if app.state.settings.environment == "development":
        log.info("background_services_skipped", reason="development_mode")
        return
    
    log.info("background_services_initializing")
    
    # Create scheduler on current running event loop (get_event_loop is deprecated in 3.10+)
    loop = asyncio.get_running_loop()
    scheduler = AsyncIOScheduler()
    scheduler.configure(event_loop=loop)
    
    # Register async jobs
    scheduler.add_job(
        sync_groups_job_async,  # async def
        trigger="interval",
        hours=1,
        args=(app.state.settings,),
        name="sync_groups",
    )
    
    # Start scheduler
    scheduler.start()
    app.state.scheduler = scheduler
    
    log.info("background_services_ready", jobs=scheduler.get_jobs())

async def sync_groups_job_async(settings):
    log = logger.bind(job="sync_groups")
    log.info("job_started")
    # Async I/O: database queries, HTTP calls
    async with aiohttp.ClientSession() as session:
        # ... fetch data
        pass
    log.info("job_completed")
```

### Option 2: Sync jobs (Legacy or CPU-bound)

```python
import structlog
from apscheduler.schedulers.background import BackgroundScheduler

logger = structlog.get_logger()

def initialize_background_services(app: FastAPI):
    """Initialize sync background task scheduler."""
    log = logger.bind(phase="background")
    
    if app.state.settings.environment == "development":
        log.info("background_services_skipped", reason="development_mode")
        return
    
    log.info("background_services_initializing")
    
    # Create scheduler (separate thread pool)
    scheduler = BackgroundScheduler(daemon=True)
    
    # Register sync jobs
    scheduler.add_job(
        sync_groups_job,  # def
        trigger="interval",
        hours=1,
        args=(app.state.settings,),
        name="sync_groups",
    )
    
    # Start scheduler
    scheduler.start()
    app.state.scheduler = scheduler
    
    log.info("background_services_ready", jobs=scheduler.get_jobs())

def sync_groups_job(settings):
    log = logger.bind(job="sync_groups")
    log.info("job_started")
    # Sync code: CPU-bound or legacy
    process_groups(settings)
    log.info("job_completed")
```

---

## Rules

- ✅ Use APScheduler 3.x for job scheduling
- ✅ Run only in production environment
- ✅ For **new jobs with I/O**: Use `AsyncIOScheduler` + `async def` jobs
- ✅ For **sync jobs**: Use `BackgroundScheduler` + `def` jobs
- ✅ Log job start/completion
- ✅ APScheduler version must be `>=3,<4` (3.x only)
- ❌ Never run jobs in development
- ❌ Never block on job execution
- ❌ Never mix sync jobs in `AsyncIOScheduler` or async jobs in `BackgroundScheduler`
