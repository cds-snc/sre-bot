"""Behaviour of the [content] settings slice under the installed configuration files."""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from infrastructure.content.settings import ContentSettings, get_content_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CONTENT__ROOT", "CONTENT__MAX_FILE_BYTES", "CONTENT__MAX_ITEMS_PER_KIND"):
        monkeypatch.delenv(name, raising=False)
    get_content_settings.cache_clear()
    yield
    get_content_settings.cache_clear()


def test_the_ceilings_default_to_the_base_file_values() -> None:
    settings = get_content_settings()

    assert (settings.max_file_bytes, settings.max_items_per_kind) == (16_384, 200)


def test_the_environment_overrides_a_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTENT__MAX_ITEMS_PER_KIND", "5")

    assert ContentSettings().max_items_per_kind == 5


@pytest.mark.parametrize("field", ["max_file_bytes", "max_items_per_kind"])
def test_a_ceiling_must_be_positive(field: str) -> None:
    with pytest.raises(ConfigurationError, match=field):
        ContentSettings(**{field: 0})


def test_a_relative_root_resolves_against_the_app_directory_and_an_absolute_one_stays() -> None:
    app = Path("/srv/app")

    assert ContentSettings(root=Path("content")).resolved_root(app) == Path("/srv/app/content")
    assert ContentSettings(root=Path("/etc/content")).resolved_root(app) == Path("/etc/content")
