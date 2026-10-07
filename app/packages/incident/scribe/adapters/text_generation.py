"""Text-generation adapter for status updates, over the OpenAI ``Summarizer``.

The status-update service depends on its own ``TextGenerator`` interface; this
is the one place that interface is bound to an integration. It becomes the
text-generation capability with TASK-134.
"""

from integrations.openai import Summarizer, get_summarizer


def build_status_update_text_generator() -> Summarizer:
    """Return the process ``Summarizer``, which satisfies ``TextGenerator``."""
    return get_summarizer()
