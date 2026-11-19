"""Singleton provider of the AI writing capability: the configured writer or the unavailable one."""

from functools import lru_cache

import structlog

from capabilities.ai_writing.adapters.openai import build_openai_writer
from capabilities.ai_writing.adapters.unconfigured import UnconfiguredAIWriter
from capabilities.ai_writing.api import AIWriter

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_ai_writer_singleton() -> AIWriter:
    """Build the writer once: OpenAI when [openai.tenant] is set, else one that reports unavailable."""
    writer = build_openai_writer()
    if writer is None:
        logger.warning("ai_writing_unconfigured")
        return UnconfiguredAIWriter()
    return writer
