"""OpenAI integration package.

Authenticated client construction, error classification, and the
``Summarizer`` behavior port with its OpenAI-backed adapter. No import-time
side effects.
"""

from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings, get_openai_settings
from integrations.openai.summarizer import (
    OpenAISummarizer,
    Summarizer,
    get_summarizer,
)

__all__ = [
    "OpenAISettings",
    "OpenAISummarizer",
    "Summarizer",
    "build_openai_client",
    "classify_openai_error",
    "get_openai_settings",
    "get_summarizer",
]
