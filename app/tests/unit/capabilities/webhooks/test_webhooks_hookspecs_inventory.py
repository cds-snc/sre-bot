"""Inventory of the webhooks capability's hookspecs: a public API a reviewed change alters.

Reads the hookspec class with pluggy's own parser, as the host does when it adds the class
in the extension-point phase; the assertions pin each hook's name and parameters.
"""

import inspect

import pluggy
import pytest

from capabilities.webhooks.hookspecs import WebhooksSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE

pytestmark = pytest.mark.unit

EXPECTED_PARAMS = {
    "register_webhook_consumers": ["self"],
    "register_webhook_handlers": ["self"],
}


def test_the_hookspecs_are_exactly_the_recorded_ones() -> None:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    hooks = {name for name in dir(WebhooksSpecs) if pm.parse_hookspec_opts(WebhooksSpecs, name) is not None}

    assert hooks == set(EXPECTED_PARAMS)


@pytest.mark.parametrize(("name", "params"), EXPECTED_PARAMS.items())
def test_each_hookspec_takes_the_recorded_parameters_and_is_documented(name: str, params: list[str]) -> None:
    hook = getattr(WebhooksSpecs, name)

    assert list(inspect.signature(hook).parameters) == params
    assert inspect.getdoc(hook)
