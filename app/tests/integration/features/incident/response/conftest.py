"""Load the response catalogue for every test in this directory, as the lifespan does at startup."""

from collections.abc import Iterator

import pytest

from features.incident.response import plugin
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service


@pytest.fixture(autouse=True)
def response_catalogues() -> Iterator[None]:
    """Answer from the EN and FR catalogues rather than a fallback, then leave the service empty again."""
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield
    reset_translation_service()
