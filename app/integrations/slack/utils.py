"""Slack integration utility functions."""

import asyncio
import functools
import hashlib
import json
from structlog import get_logger
from infrastructure.idempotency import get_idempotency_service

logger = get_logger(__name__)


def generate_slack_idempotency_key(request_body: dict) -> str:
    """Generate a consistent idempotency key for a given Slack request request_body."""
    if "trigger_id" in request_body:
        return f"slack:trigger:{request_body['trigger_id']}"

    user_id = request_body.get("user", {}).get("id", "anonymous")

    if (
        "actions" in request_body
        and isinstance(request_body["actions"], list)
        and request_body["actions"]
    ):
        action = request_body["actions"][0]
        return f"slack:action:{user_id}:{action.get('block_id', 'unknown')}:{action.get('action_id', 'unknown')}"

    if "view" in request_body:
        return (
            f"slack:view:{user_id}:{request_body['view'].get('callback_id', 'unknown')}"
        )

    payload_str = json.dumps(request_body, sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    return f"slack:generic:{payload_hash}"


def legacy_slack_listener(sync_func):
    """
    Adapter decorator for legacy synchronous Slack handlers.
    Provides automated DynamoDB idempotency checks and background thread isolation.
    """

    @functools.wraps(sync_func)
    async def async_wrapper(ack, body, *args, **kwargs):
        idempotency = get_idempotency_service()
        cache_key = generate_slack_idempotency_key(body)

        # Non-blocking check against distributed DynamoDB cache backend
        cached_response = await asyncio.to_thread(idempotency.get, cache_key)
        if cached_response:
            logger.info(
                f"Duplicate Slack event intercepted for key: {cache_key}. Dropping."
            )
            await ack()
            return

        try:
            await ack()
        except Exception as e:
            logger.error(f"Failed to clear Slack handshake: {e}")

        await asyncio.to_thread(
            idempotency.set, cache_key, {"status": "in_flight"}, ttl_seconds=30
        )

        try:
            # Shift blocking code execution onto background worker threads
            result = await asyncio.to_thread(sync_func, ack, body, *args, **kwargs)
            await asyncio.to_thread(
                idempotency.set, cache_key, {"status": "processed"}, ttl_seconds=3600
            )
            return result
        except Exception as e:
            logger.error(f"Execution failed. Evicting lock: {cache_key}")
            await asyncio.to_thread(
                idempotency.set, cache_key, {"status": "failed"}, ttl_seconds=5
            )
            raise e

    return async_wrapper
