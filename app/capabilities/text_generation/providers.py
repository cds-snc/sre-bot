"""Singleton provider of the text-generation capability: the configured generator or the unavailable one."""

from functools import lru_cache

import structlog

from capabilities.text_generation.adapters.openai import build_openai_text_generator
from capabilities.text_generation.adapters.unconfigured import UnconfiguredTextGenerator
from capabilities.text_generation.api import TextGenerator

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_text_generator_singleton() -> TextGenerator:
    """Build the generator once: OpenAI when [openai.tenant] is set, else one that reports unavailable."""
    generator = build_openai_text_generator()
    if generator is None:
        logger.warning("text_generation_unconfigured")
        return UnconfiguredTextGenerator()
    return generator
