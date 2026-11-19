"""Singleton provider of the AI writing capability: the configured writer or the unavailable one."""

from functools import lru_cache

import structlog

from capabilities.ai_writing.adapters.openai import build_openai_writer, openai_tenant_configured
from capabilities.ai_writing.adapters.unconfigured import UnconfiguredAIWriter
from capabilities.ai_writing.api import AIWriter
from capabilities.ai_writing.settings import get_ai_writing_settings

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_ai_writer_singleton() -> AIWriter:
    """Build the writer once: OpenAI when [openai.tenant] and [ai_writing] model are set, else unavailable."""
    if not openai_tenant_configured():
        logger.warning("ai_writing_unconfigured")
        return UnconfiguredAIWriter()
    model = get_ai_writing_settings().model
    if not model:
        logger.warning("ai_writing_model_unset")
        return UnconfiguredAIWriter()
    return build_openai_writer(model)
