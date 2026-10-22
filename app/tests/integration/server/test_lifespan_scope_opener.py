"""Integration tests for the lifespan's injection of the service scope opener.

The real lifespan runs with the other startup phases stubbed, as in the core
services lifespan tests. The core-services phase is replaced by one that
registers a sentinel RecordStore in the lifespan's own registry, so resolving
through the injected opener shows the opener is bound to that registry. The
provider and feature registration are recording fakes: the opener must be
injected before any feature registers its Slack handlers.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
import svcs
from fastapi import FastAPI

from contracts.records import RecordStore
from server.services import SvcsServiceScopeOpener
from tests.factories.lifespan import lifespan

pytestmark = pytest.mark.integration


async def test_lifespan_injects_one_opener_over_its_registry_before_feature_registration() -> None:
    """The provider receives one SvcsServiceScopeOpener before features register, and it resolves from the lifespan registry.

    Stub strategy: the provider is a MagicMock whose set_scope_opener and
    register_feature_integrations append to an ordered log. initialize_core_services
    is replaced by a function that registers a sentinel RecordStore in the
    registry it is given.
    Assertion rationale: one injection, of the server's opener type, that resolves
    the sentinel shows the opener wraps the lifespan's own registry; the log shows
    the injection happens before any feature registers.
    """
    order: list[str] = []
    provider = MagicMock()
    provider.app = None
    provider.set_scope_opener.side_effect = lambda _opener: order.append("set_scope_opener")
    sentinel = MagicMock(spec=RecordStore)

    async def _register_sentinel_store(registry: svcs.Registry, logger: object) -> None:
        registry.register_value(RecordStore, sentinel)

    def _record_feature_registration(**_: object) -> None:
        order.append("feature_registration")

    with ExitStack() as stack:
        stack.enter_context(patch("server.lifespan._initialize_security_services"))
        stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
        stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
        stack.enter_context(patch("server.lifespan.load_plugins"))
        stack.enter_context(patch("server.lifespan._initialize_translation_service"))
        stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
        stack.enter_context(patch("server.lifespan.initialize_core_services", _register_sentinel_store))
        stack.enter_context(patch("server.lifespan.register_feature_integrations", side_effect=_record_feature_registration))

        async with lifespan(FastAPI()):
            provider.set_scope_opener.assert_called_once()
            (opener,) = provider.set_scope_opener.call_args.args
            assert isinstance(opener, SvcsServiceScopeOpener)
            with opener.create_scope() as resolver:
                resolved = resolver.get(RecordStore)

    assert resolved is sentinel
    assert order == ["set_scope_opener", "feature_registration"]
