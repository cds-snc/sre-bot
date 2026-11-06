#!/usr/bin/env python3
"""Package generator for app/features/ and app/capabilities/.

decisions/feature-packages.md has every feature, capability and umbrella
subdomain created in one shape by a generator, so a new contributor is
productive in an afternoon. This writes the package from the templates in
bin/package_templates/ and makes every edit the package needs elsewhere:

  - a plugin (feature, capability, subdomain): its entry point (dotted for a
    subdomain), its module in the protected-plugins contract and its
    enablement key, switched on, in the [plugins.<area>] table chosen;
  - a feature or umbrella: the feature-independence contract; an umbrella also
    gets its own exhaustive layers contract, and a subdomain, core/ or common/
    joins it;
  - the first capability creates app/capabilities/ and adds it to the
    import-linter root packages, the wheel packages and contracts (b) and (e).

The TOML edits go through bin/package_toml.py, which keeps comments and checks
the result before writing; any refusal writes nothing. The generated package
passes bin/check_package_shape.py with an empty baseline.

Usage:
    make new-package                               # asks for each value
    python3 -m bin.new_package feature <name> --area <area> [--settings]
    python3 -m bin.new_package capability <name> --area <area> --classification generic|supporting \
        --consumer features.<feature>[.<subdomain>] [--consumer ...] [--settings]
    python3 -m bin.new_package umbrella <name> --area <area>
    python3 -m bin.new_package subdomain <umbrella>.<name> --area <area> [--settings]
    python3 -m bin.new_package core|common <umbrella> [--settings]
"""

import argparse
import keyword
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from bin.package_toml import (
    Edit,
    TomlEditError,
    UmbrellaMember,
    capabilities_root,
    enablement_key,
    entry_point,
    independent_feature,
    plugin_areas,
    protected_plugin,
    render,
    settings_table,
    umbrella_contract,
    umbrella_member,
)

APP_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Path(__file__).resolve().parent / "package_templates"
FEATURES = "features"
CAPABILITIES = "capabilities"
KINDS = ("feature", "capability", "umbrella", "subdomain", "core", "common")
PLUGIN_KINDS = frozenset({"feature", "capability", "subdomain"})
AREA_KINDS = PLUGIN_KINDS | {"umbrella"}
UMBRELLA_MEMBER_KINDS: dict[str, UmbrellaMember] = {"subdomain": "subdomain", "core": "core", "common": "common"}
CLASSIFICATIONS = ("generic", "supporting")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
CONSUMER = re.compile(r"^features\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")
# A subdomain named like a layout-table directory or an umbrella kernel would be read as one.
RESERVED_SUBDOMAINS = frozenset({"core", "common", "adapters", "entrypoints", "locales", "service", "domain"})


class GeneratorError(Exception):
    """The request is refused; nothing was written."""


@dataclass(frozen=True)
class Request:
    """One package to create, as parsed from the command line."""

    kind: str
    target: str
    root: Path
    area: str | None = None
    classification: str | None = None
    consumers: tuple[str, ...] = ()
    settings: bool = False


@dataclass(frozen=True)
class Package:
    """Where a request's package goes and the names it is known by."""

    directory: Path
    module: str
    umbrella: str | None
    name: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="new_package", description="Create a package in the feature-packages shape.")
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("target", help="<name>; <umbrella>.<name> for a subdomain; <umbrella> for core or common")
    parser.add_argument("--area", help="product area: a [plugins.<area>] table in config/base.toml")
    parser.add_argument("--classification", help="capability only: generic or supporting")
    parser.add_argument("--consumer", action="append", default=[], help="capability only: features.<feature>[.<subdomain>]")
    parser.add_argument("--settings", action="store_true", help="add settings.py and its [<table>] in base.toml")
    parser.add_argument("--root", type=Path, default=APP_ROOT, help=argparse.SUPPRESS)
    return parser


def parse_request(argv: list[str]) -> Request:
    """Parse command-line arguments into a request; validation happens in ``generate``."""
    args = _parser().parse_args(argv)
    return Request(
        kind=args.kind,
        target=args.target,
        root=args.root,
        area=args.area,
        classification=args.classification,
        consumers=tuple(args.consumer),
        settings=args.settings,
    )


def _check_name(name: str) -> None:
    if not NAME.fullmatch(name) or keyword.iskeyword(name):
        raise GeneratorError(f"'{name}' is not a lower snake_case Python identifier")


def _umbrella_directory(root: Path, umbrella: str) -> Path:
    _check_name(umbrella)
    directory = root / FEATURES / umbrella
    if not directory.is_dir():
        raise GeneratorError(f"no umbrella '{umbrella}' under features/; create it first: new_package umbrella {umbrella}")
    return directory


def _locate(request: Request) -> Package:
    root = request.root
    match request.kind:
        case "feature" | "umbrella" | "capability":
            _check_name(request.target)
            top = CAPABILITIES if request.kind == "capability" else FEATURES
            package = Package(root / top / request.target, f"{top}.{request.target}", None, request.target)
        case "subdomain":
            umbrella, _, name = request.target.partition(".")
            if not name or "." in name:
                raise GeneratorError(f"a subdomain is named <umbrella>.<subdomain>, not '{request.target}'")
            _check_name(name)
            if name in RESERVED_SUBDOMAINS:
                raise GeneratorError(f"'{name}' is reserved for an umbrella kernel or a layout-table directory")
            directory = _umbrella_directory(root, umbrella) / name
            package = Package(directory, f"{FEATURES}.{umbrella}.{name}", umbrella, name)
        case _:
            umbrella = request.target
            directory = _umbrella_directory(root, umbrella) / request.kind
            package = Package(directory, f"{FEATURES}.{umbrella}.{request.kind}", umbrella, request.kind)
    if package.directory.exists():
        raise GeneratorError(f"{package.directory.relative_to(root)} already exists")
    return package


def _entry_point_name(package: Package) -> str:
    return f"{package.umbrella}.{package.name}" if package.umbrella else package.name


def _table(package: Package) -> str:
    return "_".join(package.module.split(".")[1:])


def _title(text: str) -> str:
    return text.replace("_", " ").replace(".", " ").capitalize()


def _check_capability(request: Request) -> None:
    if request.classification not in CLASSIFICATIONS:
        raise GeneratorError(f"a capability's classification must be one of {', '.join(CLASSIFICATIONS)}")
    if not request.consumers:
        raise GeneratorError("a capability names at least one --consumer features.<feature>[.<subdomain>]")
    for consumer in request.consumers:
        if not CONSUMER.fullmatch(consumer) or not request.root.joinpath(*consumer.split(".")).is_dir():
            raise GeneratorError(f"consumer '{consumer}' names no package under features/")


def _pyproject_edits(request: Request, package: Package, pyproject: dict[str, Any]) -> list[Edit]:
    edits: list[Edit] = []
    if request.kind == "capability":
        edits += capabilities_root(pyproject)
    if request.kind in PLUGIN_KINDS:
        edits += entry_point(pyproject, _entry_point_name(package), package.module)
        edits += protected_plugin(pyproject, package.module)
    if request.kind in ("feature", "umbrella"):
        edits += independent_feature(pyproject, package.module)
    if request.kind == "umbrella":
        edits += umbrella_contract(pyproject, package.name)
    member_kind = UMBRELLA_MEMBER_KINDS.get(request.kind)
    if member_kind and package.umbrella:
        edits += umbrella_member(pyproject, package.umbrella, package.name, member_kind)
    return edits


def _base_edits(request: Request, package: Package, base: dict[str, Any]) -> list[Edit]:
    edits: list[Edit] = []
    if request.kind in PLUGIN_KINDS:
        edits += enablement_key(base, request.area or "", _entry_point_name(package))
    if request.settings:
        table = _table(package)
        if table in base:
            raise GeneratorError(f"config/base.toml already has a [{table}] table; another slice owns it")
        edits += settings_table(base, table)
    return edits


def _template_values(request: Request, package: Package) -> dict[str, str]:
    table = _table(package)
    labels = {"feature": "feature", "capability": "capability", "subdomain": "subdomain"}
    return {
        "title": _title(table),
        "label": labels.get(request.kind, request.kind),
        "module": package.module,
        "umbrella": f"{FEATURES}.{package.umbrella}" if package.umbrella else "",
        "table": table,
        "settings_class": "".join(part.capitalize() for part in table.split("_")) + "Settings",
        "env_prefix": f"{table.upper()}__",
        "classification": request.classification or "",
        "consumers": "\n".join(f"- {consumer}" for consumer in request.consumers),
        "test_path": "/".join(package.module.split(".")),
    }


def _files(request: Request) -> dict[str, str]:
    """Generated path (relative to the package) -> template file name; '' writes an empty file."""
    plugin = {
        "__init__.py": "plugin_init.py.tmpl",
        "README.md": "feature_readme.md.tmpl",
        "service.py": "service.py.tmpl",
        "interfaces.py": "interfaces.py.tmpl",
        "entrypoints/__init__.py": "entrypoints_init.py.tmpl",
    }
    files: dict[str, str] = {
        "feature": plugin,
        "subdomain": plugin,
        "capability": plugin
        | {"README.md": "capability_readme.md.tmpl", "api.py": "api.py.tmpl", "hookspecs.py": "hookspecs.py.tmpl"},
        "umbrella": {"__init__.py": "", "README.md": "umbrella_readme.md.tmpl"},
        "core": {
            "__init__.py": "core_init.py.tmpl",
            "api.py": "core_api.py.tmpl",
            "service.py": "service.py.tmpl",
            "interfaces.py": "interfaces.py.tmpl",
        },
        "common": {"__init__.py": "common_init.py.tmpl"},
    }[request.kind]
    if request.settings and request.kind != "umbrella":
        files = files | {"settings.py": "settings.py.tmpl"}
    return files


def _product_scope_line(request: Request, package: Package) -> str | None:
    if request.kind not in ("feature", "capability", "umbrella") or not request.area:
        return None
    label = _title(request.area)
    token = f"`{package.name}`" + {"feature": "", "capability": " capability", "umbrella": " umbrella"}[request.kind]
    scope = request.root.parent / "decisions" / "product-scope.md"
    if scope.is_file():
        for line in scope.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"| {label} |"):
                return line.rstrip().removesuffix("|").rstrip() + f", {token} |"
    return f"add {token} to the '{label}' row"


def generate(request: Request) -> list[str]:
    """Create the package and its TOML edits, or raise ``GeneratorError`` having written nothing."""
    package = _locate(request)
    if request.kind in AREA_KINDS and not request.area:
        raise GeneratorError(f"--area is required for a {request.kind}")
    if request.kind == "capability":
        _check_capability(request)

    pyproject_path = request.root / "pyproject.toml"
    base_path = request.root / "config" / "base.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    base_text = base_path.read_text(encoding="utf-8")
    base = tomllib.loads(base_text)
    if request.kind == "umbrella" and request.area not in plugin_areas(base):
        raise GeneratorError(f"no [plugins.{request.area}] table; choose one of: {', '.join(plugin_areas(base))}")
    try:
        pyproject_edits = _pyproject_edits(request, package, tomllib.loads(pyproject_text))
        base_edits = _base_edits(request, package, base)
        new_pyproject = render(pyproject_text, pyproject_edits)
        new_base = render(base_text, base_edits)
    except TomlEditError as error:
        raise GeneratorError(str(error)) from error

    values = _template_values(request, package)
    rendered = {
        package.directory / relative: Template((TEMPLATES / template).read_text(encoding="utf-8")).substitute(values)
        if template
        else ""
        for relative, template in _files(request).items()
    }
    if request.kind == "capability" and not (request.root / CAPABILITIES).is_dir():
        rendered[request.root / CAPABILITIES / "__init__.py"] = ""
    for path, content in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if pyproject_edits:
        pyproject_path.write_text(new_pyproject, encoding="utf-8")
    if base_edits:
        base_path.write_text(new_base, encoding="utf-8")
    return _report(request, package)


def _report(request: Request, package: Package) -> list[str]:
    lines = [f"Created {package.directory.relative_to(request.root)}/ ({package.module})."]
    if request.kind in PLUGIN_KINDS:
        name = _entry_point_name(package)
        lines += [
            f"Entry point '{name}' = '{package.module}'; enablement key [plugins.{request.area}] \"{name}\" = true.",
            "Run 'uv sync' so the new entry point is installed before the app boots.",
        ]
    scope_line = _product_scope_line(request, package)
    if scope_line:
        lines.append(f"decisions/product-scope.md, add to the table: {scope_line}")
    if request.settings:
        lines.append(f"settings.py reads [{_table(package)}] in config/base.toml; add its keys to both.")
    lines.append(
        f"Next: write the README, declare requirements, add tests under tests/unit/{_template_values(request, package)['test_path']}/; "
        "then make check-package-shape check-import-contracts check-settings-key-ownership."
    )
    return lines


def _ask(prompt: str) -> str:
    return input(f"{prompt}: ").strip()


def prompt_arguments() -> list[str]:
    """Ask for each value on a terminal; return them as command-line arguments."""
    kind = _ask(f"Kind ({' / '.join(KINDS)})")
    hints = {"subdomain": "<umbrella>.<subdomain>", "core": "umbrella", "common": "umbrella"}
    argv = [kind, _ask(f"Name ({hints.get(kind, 'lower snake_case')})")]
    if kind in AREA_KINDS:
        base = tomllib.loads((APP_ROOT / "config" / "base.toml").read_text(encoding="utf-8"))
        argv += ["--area", _ask(f"Product area ({' / '.join(plugin_areas(base))})")]
    if kind == "capability":
        argv += ["--classification", _ask(f"Classification ({' / '.join(CLASSIFICATIONS)})")]
        for consumer in _ask("Feature consumers (features.<feature>[.<subdomain>], comma-separated)").split(","):
            argv += ["--consumer", consumer.strip()]
    if kind != "umbrella" and _ask("Settings slice? (y/N)").lower().startswith("y"):
        argv.append("--settings")
    return argv


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
        if not argv and sys.stdin.isatty():
            argv = prompt_arguments()
    try:
        lines = generate(parse_request(argv))
    except GeneratorError as error:
        print(f"new_package: {error}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
