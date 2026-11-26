"""Unit tests for registering the sender kinds as provisioned content.

The plugin's hookimpl registers into a real loader over a temporary content root, so the
test sees what boot would: an optional kind that loads nothing when no file exists, and a
valid file built into a ``SenderKind``. The language test pins the file model's languages to
the app's supported catalogue languages.
"""

from pathlib import Path

import pytest
import yaml

from capabilities.webhooks import plugin
from capabilities.webhooks.domain.kinds import SenderKind
from capabilities.webhooks.schemas import LocalizedTemplateFile
from infrastructure.content.loader import ContentLoader
from infrastructure.i18n.models import Locale
from tests.unit.capabilities.webhooks.conftest import kind_document

pytestmark = pytest.mark.unit


def _loader(root: Path) -> ContentLoader:
    loader = ContentLoader(root, max_file_bytes=16384, max_items_per_kind=200)
    plugin.register_content_kinds(loader)
    return loader


def test_the_kind_is_registered_optional_under_the_webhooks_owner(tmp_path: Path) -> None:
    (kind,) = _loader(tmp_path).kinds

    assert (kind.key, kind.required, kind.max_file_bytes, kind.max_items) == ("webhooks/sender-kinds", False, 16384, 200)


def test_no_sender_kind_files_loads_nothing(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    (kind,) = loader.kinds

    assert dict(loader.load().items(kind)) == {}


def test_a_sender_kind_file_loads_as_a_sender_kind(tmp_path: Path) -> None:
    path = tmp_path / "webhooks" / "sender-kinds" / "aws" / "budget-alert.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(kind_document(), allow_unicode=True), encoding="utf-8")

    loader = _loader(tmp_path)
    (kind,) = loader.kinds
    items = loader.load().items(kind)

    assert isinstance(items["budget-alert"], SenderKind)


def test_the_template_languages_are_the_supported_languages() -> None:
    """A language the app gains must be added to the file model, as to every catalogue."""
    aliases = {field.alias for field in LocalizedTemplateFile.model_fields.values()}

    assert aliases == {locale.value for locale in Locale}
