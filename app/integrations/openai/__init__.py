"""OpenAI integration package.

Authenticated client construction and error classification. The AI writing
capability's OpenAI adapter is its only consumer (import-linter contract (o)). No
import-time side effects.
"""

from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings, get_openai_settings

__all__ = [
    "OpenAISettings",
    "build_openai_client",
    "classify_openai_error",
    "get_openai_settings",
]
