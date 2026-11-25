"""JSON Schema text for each content kind, shared by the export and the drift check.

The app owns one generated set at ``content/schemas/<owner>/<name>.json``; editors map
content globs to it and a deployment repository validates against it with the app's own
command (``python -m bin.check_content_schemas``).
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from contracts.content import ContentKind


def schema_text(kind: ContentKind[Any, Any]) -> str:
    """Return the kind's JSON Schema as stable text: sorted keys, two-space indent, trailing newline."""
    return json.dumps(kind.model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def schema_path(schemas_directory: Path, kind: ContentKind[Any, Any]) -> Path:
    """Return where the kind's schema file lives under ``schemas_directory``."""
    return schemas_directory / kind.owner / f"{kind.name}.json"


def schema_drift(kinds: Iterable[ContentKind[Any, Any]], schemas_directory: Path) -> list[str]:
    """Return one line per kind whose checked-in schema is missing or differs from its model."""
    drift: list[str] = []
    for kind in kinds:
        path = schema_path(schemas_directory, kind)
        if not path.is_file():
            drift.append(f"{kind.key}: schema file {path} is missing")
        elif path.read_text(encoding="utf-8") != schema_text(kind):
            drift.append(f"{kind.key}: schema file {path} differs from the model")
    return drift


def write_schemas(kinds: Iterable[ContentKind[Any, Any]], directory: Path) -> list[Path]:
    """Write every kind's schema under ``directory`` and return the files written."""
    written: list[Path] = []
    for kind in kinds:
        path = schema_path(directory, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(schema_text(kind), encoding="utf-8")
        written.append(path)
    return written
