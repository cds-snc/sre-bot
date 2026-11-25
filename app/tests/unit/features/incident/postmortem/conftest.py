"""Load the postmortem catalogue for every test in this directory, as the lifespan loads plugin catalogues at startup."""

from collections.abc import Iterator

import pytest

from features.incident.postmortem.entrypoints.texts import register_catalogue
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service


@pytest.fixture(autouse=True)
def postmortem_catalogues() -> Iterator[None]:
    """Render wording from the EN and FR catalogues rather than a fallback, then leave the service empty again."""
    load_plugin_catalogues(register_catalogue)
    yield
    reset_translation_service()
