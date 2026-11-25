"""Provisioned-content loader: reads each registered kind's files into a frozen catalogue.

Files are untrusted input. A file is read only when it is a regular ``.yaml`` file under
the kind's own directory, within the size limit; it is parsed with a safe loader that
refuses duplicate mapping keys, checked for its ``kind`` and ``version``, then validated
by the kind's file model. Every problem is collected and raised once, so a deployment
fixes them in one pass; a problem names the file and field, never the input value.
"""

import os
from collections.abc import Hashable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from pydantic import ValidationError

from contracts.content import ContentCatalogue, ContentDocument, ContentKind, ContentLoadError, ContentProblem

YAML_SUFFIX = ".yaml"


class _StrictLoader(yaml.SafeLoader):
    """A safe loader that refuses a mapping key written twice (PyYAML otherwise keeps the last)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, Hashable):
                raise yaml.constructor.ConstructorError(None, None, "found an unhashable mapping key", key_node.start_mark)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, "found a duplicate mapping key", key_node.start_mark)
            seen.add(key)
        mapping: dict[Any, Any] = super().construct_mapping(node, deep=deep)
        return mapping


class LoadedContentCatalogue(ContentCatalogue):
    """The catalogue the loader returns: each kind's built items by id, read-only."""

    def __init__(self, items: Mapping[str, Mapping[str, Any]]) -> None:
        self._items = items

    def items[T](self, kind: ContentKind[Any, T]) -> Mapping[str, T]:
        """Return the kind's items by id, empty when none were loaded."""
        return self._items.get(kind.key, MappingProxyType({}))


class ContentLoader:
    """Collects the registered kinds and loads their files from a content root."""

    def __init__(self, root: Path, *, max_file_bytes: int, max_items_per_kind: int) -> None:
        self._root = root
        self._max_file_bytes = max_file_bytes
        self._max_items = max_items_per_kind
        self._kinds: dict[str, ContentKind[Any, Any]] = {}

    @property
    def kinds(self) -> tuple[ContentKind[Any, Any], ...]:
        """The registered kinds, in registration order."""
        return tuple(self._kinds.values())

    def register(self, kind: ContentKind[Any, Any]) -> None:
        """Register a kind; a second kind with the same owner and name is refused."""
        if kind.key in self._kinds:
            raise ValueError(f"content kind {kind.key} is registered twice")
        self._kinds[kind.key] = kind

    def load(self) -> ContentCatalogue:
        """Load every registered kind's files; raise ``ContentLoadError`` listing every problem.

        With no kind registered nothing is read, so a missing root is not an error.
        """
        problems: list[ContentProblem] = []
        loaded: dict[str, Mapping[str, Any]] = {}
        for kind in self._kinds.values():
            loaded[kind.key] = MappingProxyType(self._load_kind(kind, problems))
        if problems:
            raise ContentLoadError(tuple(problems))
        return LoadedContentCatalogue(loaded)

    def _load_kind(self, kind: ContentKind[Any, Any], problems: list[ContentProblem]) -> dict[str, Any]:
        files = self._discover(kind, problems)
        limit = min(self._max_items, kind.max_items or self._max_items)
        if len(files) > limit:
            problems.append(ContentProblem(kind.key, kind.key, "", f"{len(files)} files exceed the limit of {limit} items"))
            return {}
        items: dict[str, Any] = {}
        origins: dict[str, str] = {}
        for path in files:
            name = self._relative(path)
            item = self._load_file(kind, path, name, problems)
            if item is None:
                continue
            item_id, built = item
            if item_id in items:
                problems.append(ContentProblem(kind.key, name, "id", f"duplicates the id of {origins[item_id]}"))
                continue
            items[item_id] = built
            origins[item_id] = name
        if kind.required and not files:
            problems.append(ContentProblem(kind.key, kind.key, "", "required kind has no items"))
        return items

    def _discover(self, kind: ContentKind[Any, Any], problems: list[ContentProblem]) -> list[Path]:
        """Return the kind's ``.yaml`` files, refusing symlinks and other file types, sorted."""
        base = self._root / kind.owner / kind.name
        if not base.exists() and not base.is_symlink():
            return []
        if not base.is_symlink() and not base.is_dir():
            problems.append(ContentProblem(kind.key, self._relative(base), "", "a kind's path must be a directory"))
            return []
        found: list[Path] = []
        pending = [base]
        root = self._root.resolve()
        while pending:
            directory = pending.pop()
            if directory.is_symlink() or not directory.resolve().is_relative_to(root):
                problems.append(
                    ContentProblem(kind.key, self._relative(directory), "", "symlinks and paths outside the root are refused")
                )
                continue
            with os.scandir(directory) as entries:
                for entry in sorted(entries, key=lambda candidate: candidate.name):
                    path = Path(entry.path)
                    if entry.is_symlink():
                        problems.append(
                            ContentProblem(kind.key, self._relative(path), "", "symlinks and paths outside the root are refused")
                        )
                    elif entry.is_dir():
                        pending.append(path)
                    elif path.suffix != YAML_SUFFIX:
                        problems.append(ContentProblem(kind.key, self._relative(path), "", f"only {YAML_SUFFIX} files are read"))
                    else:
                        found.append(path)
        return sorted(found)

    def _load_file(
        self, kind: ContentKind[Any, Any], path: Path, name: str, problems: list[ContentProblem]
    ) -> tuple[str, Any] | None:
        limit = min(self._max_file_bytes, kind.max_file_bytes or self._max_file_bytes)
        if path.stat().st_size > limit:
            problems.append(ContentProblem(kind.key, name, "", f"file exceeds the limit of {limit} bytes"))
            return None
        document = self._parse(kind, path, name, problems)
        if document is None:
            return None
        model = self._validate(kind, document, path, name, problems)
        if model is None:
            return None
        try:
            return model.id, kind.build(model)
        except ValueError:
            problems.append(ContentProblem(kind.key, name, "", "the item could not be built from the file"))
            return None

    def _parse(self, kind: ContentKind[Any, Any], path: Path, name: str, problems: list[ContentProblem]) -> dict[str, Any] | None:
        try:
            document = yaml.load(path.read_bytes().decode("utf-8"), Loader=_StrictLoader)  # noqa: S506 - the loader is a SafeLoader
        except UnicodeDecodeError:
            problems.append(ContentProblem(kind.key, name, "", "the file is not valid UTF-8"))
            return None
        except yaml.YAMLError as error:
            line = (
                f" at line {error.problem_mark.line + 1}"
                if isinstance(error, yaml.MarkedYAMLError) and error.problem_mark
                else ""
            )
            reason = error.problem if isinstance(error, yaml.MarkedYAMLError) and error.problem else "invalid YAML"
            problems.append(ContentProblem(kind.key, name, "", f"invalid YAML{line}: {reason}"))
            return None
        if not isinstance(document, dict):
            problems.append(ContentProblem(kind.key, name, "", "the file must hold one mapping"))
            return None
        return document

    def _validate(
        self, kind: ContentKind[Any, Any], document: dict[str, Any], path: Path, name: str, problems: list[ContentProblem]
    ) -> ContentDocument | None:
        before = len(problems)
        if document.get("kind") != kind.key:
            problems.append(ContentProblem(kind.key, name, "kind", f"must be {kind.key}, the kind of its directory"))
        version = document.get("version")
        if isinstance(version, bool) or version not in kind.versions:
            supported = ", ".join(str(number) for number in sorted(kind.versions))
            problems.append(ContentProblem(kind.key, name, "version", f"unsupported version; supported: {supported}"))
        if len(problems) > before:
            return None
        try:
            model: ContentDocument = kind.model.model_validate(document)
        except ValidationError as error:
            problems.extend(
                ContentProblem(kind.key, name, ".".join(str(part) for part in detail["loc"]), detail["msg"])
                for detail in error.errors()
            )
            return None
        if model.id != path.stem:
            problems.append(ContentProblem(kind.key, name, "id", "must equal the file name without its extension"))
            return None
        return model

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(self._root).as_posix()
        except ValueError:
            return path.name
