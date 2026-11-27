#!/usr/bin/env python3
"""Generated-schema and content check for provisioned content.

decisions/provisioned-content.md has the app own one generated JSON Schema per content
kind at ``content/schemas/<owner>/<kind>.json``. This command, run over any content
root, is the one validator a deployment repository also runs from the pinned image:

  - schema drift: the checked-in schema of every registered kind equals the schema its
    file model generates (sorted keys, two-space indent, trailing newline);
  - content: every item under each ``--root`` loads with the same loader the app boots with.

With no kind registered there is nothing to compare or load, and the check passes.

Usage:
    python -m bin.check_content_schemas [--root PATH ...] [--write] [--export DIR]

    --root PATH    a content root to validate (repeatable; default: content/ and content/examples/)
    --write        regenerate the checked-in schemas, then check
    --export DIR   write the schemas under DIR (for a deployment repository's editors), then check
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import structlog

from contracts.content import ContentKind, ContentLoadError
from infrastructure.content.loader import ContentLoader
from infrastructure.content.schema import schema_drift, write_schemas
from infrastructure.content.settings import ContentSettings
from server.plugins.boot import call_hook_per_plugin
from server.plugins.manager import get_plugin_manager, load_plugins

APP_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIRECTORY = APP_ROOT / "content" / "schemas"
DEFAULT_ROOTS = (APP_ROOT / "content", APP_ROOT / "content" / "examples")


def collect_kinds() -> tuple[ContentKind[Any, Any], ...]:
    """Load the plugins as the app does and return the kinds they register."""
    logger = structlog.get_logger()
    pm = get_plugin_manager()
    load_plugins(pm, frozenset(), logger)
    collector = ContentLoader(APP_ROOT / "content", **_ceilings())
    call_hook_per_plugin(pm, "register_content_kinds", logger, registrar=collector)
    return collector.kinds


def check_content(kinds: Sequence[ContentKind[Any, Any]], roots: Sequence[Path]) -> list[str]:
    """Load every kind from each root and return one line per problem found."""
    lines: list[str] = []
    for root in roots:
        loader = ContentLoader(root, **_ceilings())
        for kind in kinds:
            loader.register(kind)
        try:
            loader.load()
        except ContentLoadError as error:
            lines.extend(f"{root}: {p.kind}: {p.file}: {p.field or '-'}: {p.message}" for p in error.problems)
    return lines


def run(
    kinds: Sequence[ContentKind[Any, Any]],
    *,
    roots: Sequence[Path],
    schemas_directory: Path,
    write: bool = False,
    export: Path | None = None,
) -> list[str]:
    """Write the requested schemas, then return every drift and content problem as lines."""
    if write:
        write_schemas(kinds, schemas_directory)
    if export is not None:
        write_schemas(kinds, export)
    return [*schema_drift(kinds, schemas_directory), *check_content(kinds, roots)]


def _ceilings() -> dict[str, int]:
    fields = ContentSettings.model_fields
    return {"max_file_bytes": fields["max_file_bytes"].default, "max_items_per_kind": fields["max_items_per_kind"].default}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, action="append", dest="roots")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    kinds = collect_kinds()
    problems = run(
        kinds,
        roots=args.roots or DEFAULT_ROOTS,
        schemas_directory=SCHEMAS_DIRECTORY,
        write=args.write,
        export=args.export,
    )
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"content schemas ok ({len(kinds)} kind(s) registered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
