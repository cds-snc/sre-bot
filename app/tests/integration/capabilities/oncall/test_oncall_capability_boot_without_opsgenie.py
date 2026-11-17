"""Integration test: the on-call capability boots and answers with no Opsgenie settings.

The real lifespan runs on a freshly built plugin manager with core services, security, directory,
Slack provider and feature registration stubbed, as the plugin-loading tests do. Rotation files
come from a ``tmp_path`` directory through the loader's directory argument. Assertions are on the
plugin being registered (the pinned test environment enables it with no ``[opsgenie.tenant]``),
the self-managed source answering from the fixture files and Opsgenie answering a result, not an error.
"""

import json
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from capabilities.oncall.adapters.opsgenie import OpsgenieSource
from capabilities.oncall.adapters.rotations import RotationsSource, load_rotation_schedules
from capabilities.oncall.api import configured_rotations, get_oncall_lookup
from capabilities.oncall.domain import OPSGENIE, ROTATIONS, ScheduleReference
from capabilities.oncall.providers import get_oncall_service, get_rotation_schedules
from capabilities.oncall.service import OnCallService
from contracts.operations.codes import ErrorCode
from integrations.opsgenie.settings import OpsGenieSettings
from server.plugins.manager import get_plugin_manager
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fresh_providers() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    get_oncall_service.cache_clear()
    get_rotation_schedules.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    get_oncall_service.cache_clear()
    get_rotation_schedules.cache_clear()


def _stub_startup(stack: ExitStack) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan.initialize_core_services"))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))


async def test_the_capability_registers_and_the_rotations_source_answers_without_opsgenie(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps({"slack-usergroup-handle": "oncall-a", "slack-usergroup-name": "On-call A", "members": ["U1"]})
    )
    assert OpsGenieSettings().tenant is None

    with ExitStack() as stack:
        _stub_startup(stack)
        async with lifespan(FastAPI()):
            pm = get_plugin_manager()
            registered = {pm.get_name(plugin) for plugin, _ in pm.list_plugin_distinfo()}
            service = OnCallService(
                {ROTATIONS: RotationsSource(load_rotation_schedules(tmp_path)), OPSGENIE: OpsgenieSource()},
            )
            rotations = await service.on_call_now(ScheduleReference(ROTATIONS, "oncall-a"))
            opsgenie = await service.on_call_now(ScheduleReference(OPSGENIE, "sched-1"))

    assert "oncall" in registered
    assert rotations.is_success
    assert rotations.data is not None
    assert rotations.data[0].account is not None
    assert rotations.data[0].account.account_id == "U1"
    assert opsgenie.error_code == ErrorCode.CONFIG_NOT_CONFIGURED


async def test_the_provider_and_the_config_time_accessor_agree_on_the_packaged_rotation_files() -> None:
    lookup = get_oncall_lookup()

    result = await lookup.list_schedules(ROTATIONS)

    assert result.is_success
    assert result.data == configured_rotations()
    assert ScheduleReference(ROTATIONS, "canadalogin-website-atc") in configured_rotations()
