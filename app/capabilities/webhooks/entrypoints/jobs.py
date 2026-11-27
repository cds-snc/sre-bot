"""The inbox sweeper job: retries due items, takes over expired leases, dead-letters past the cap.

A Tier-2 interval job: each run takes the scheduler's lease, so one replica sweeps at a time;
the item guards make a duplicate run harmless anyway (decisions/reliability.md). The job body
is sync and runs on the scheduler's thread, so each run opens one ``asyncio.Runner`` and builds
its async clients (the SNS port, the posters) inside that run, closing them at its end. A
failure reaches the scheduler's error boundary, which logs it once.

``register_sweeper`` is not called yet: the inbox table must exist before any item does.
TODO(TASK-37.4.3): call register_sweeper from a register_background_jobs hookimpl.
"""

import asyncio
from datetime import timedelta

import structlog

from capabilities.webhooks.providers import build_channel_posters, build_processor, build_sns_http
from capabilities.webhooks.settings import get_webhooks_settings
from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.services import ServiceResolver, ServiceScopeOpener

logger = structlog.get_logger()

SWEEPER_JOB = "webhooks_inbox_sweeper"


async def _sweep(services: ServiceResolver) -> int:
    sns = build_sns_http()
    try:
        processor = build_processor(services, confirmer=sns, posters=build_channel_posters())
        return await processor.sweep()
    finally:
        await sns.aclose()


def run_sweeper(scopes: ServiceScopeOpener) -> None:
    """One sweep: one service scope and one event loop for the whole run."""
    with scopes.create_scope() as services, asyncio.Runner() as runner:
        taken = runner.run(_sweep(services))
    logger.info("webhook_sweep_completed", taken=taken)


def register_sweeper(registry: BackgroundJobRegistry) -> None:
    """Register the sweeper as a leased interval job, its timing from [webhooks]."""
    settings = get_webhooks_settings()
    scopes = registry.service_scopes
    registry.register_interval(
        job_name=SWEEPER_JOB,
        every=timedelta(seconds=settings.sweeper_interval_seconds),
        job=lambda: run_sweeper(scopes),
        lease_ttl=timedelta(seconds=settings.sweeper_lease_ttl_seconds),
    )
