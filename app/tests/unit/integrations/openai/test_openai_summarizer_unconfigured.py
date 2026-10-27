"""Unit tests for the OpenAI summarizer when OpenAI is not configured.

With no [openai.tenant] entry the summarizer answers with a permanent CONFIG_NOT_CONFIGURED
result and never builds a client: the client factory is replaced by a mock that must stay
uncalled, and the captured log lines are searched for the key value set beside the empty
entry's absence.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.openai.settings import OpenAISettings
from integrations.openai.summarizer import OpenAISummarizer
from tests.unit.integrations.openai.conftest import install_openai_files

pytestmark = pytest.mark.unit


async def test_no_tenant_returns_not_configured_without_a_client(tmp_path: Path) -> None:
    install_openai_files(tmp_path)
    settings = OpenAISettings()

    with patch("integrations.openai.summarizer.build_openai_client") as build, capture_logs() as entries:
        result = await OpenAISummarizer(settings=settings).summarize("transcript")

    build.assert_not_called()
    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert "sk-" not in repr(entries)
