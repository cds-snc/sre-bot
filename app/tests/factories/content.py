"""A test-only content kind and helpers to lay out its files under a temporary root."""

from dataclasses import dataclass
from pathlib import Path

from contracts.content import ContentDocument, ContentKind


class WidgetDocument(ContentDocument):
    """File model of the test-only kind."""

    title: str


@dataclass(frozen=True)
class Widget:
    """The frozen item the test-only kind builds."""

    id: str
    title: str


def build_widget(document: WidgetDocument) -> Widget:
    return Widget(id=document.id, title=document.title)


WIDGETS = ContentKind(owner="probe", name="widgets", model=WidgetDocument, build=build_widget)
GADGETS = ContentKind(owner="probe", name="gadgets", model=WidgetDocument, build=build_widget)


def widget_text(item_id: str, title: str = "A title", *, kind: str = "probe/widgets", version: int = 1) -> str:
    """Return the text of a valid file for the test-only kind."""
    return f"kind: {kind}\nversion: {version}\nid: {item_id}\ntitle: {title}\n"


def write_item(root: Path, kind: ContentKind, relative: str, text: str) -> Path:
    """Write ``text`` to ``<root>/<owner>/<name>/<relative>`` and return the path."""
    path = root / kind.owner / kind.name / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
