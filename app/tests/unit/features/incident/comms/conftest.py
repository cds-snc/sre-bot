"""Load the comms catalogue for every test in this directory, as the lifespan does at startup."""

from collections.abc import Iterator

import pytest

import features.incident.comms as comms_pkg
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service


@pytest.fixture(autouse=True)
def comms_catalogues() -> Iterator[None]:
    """Render views from the EN and FR catalogues rather than a fallback, then leave the service empty again."""
    load_plugin_catalogues(comms_pkg.register_i18n_resources)
    yield
    reset_translation_service()
