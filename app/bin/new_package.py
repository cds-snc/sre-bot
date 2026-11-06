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
    import-linter root packages, the wheel packages and every contract that
    lists features; a capability's area comes from its consumers' keys;
  - promote turns a flat plugin feature into an umbrella in place: its code
    becomes the first subdomain, settings.py moves to common/ (same table),
    references are rewritten, and its entry point and keys are renamed.

The TOML edits go through bin/package_toml.py, which keeps comments and checks
the result before writing; any refusal writes nothing. The generated package
passes bin/check_package_shape.py with an empty baseline.

Usage:
    make new-package                               # asks for each value
    python3 -m bin.new_package feature <name> --area <area> [--settings]
    python3 -m bin.new_package capability <name> [--area <area>] --classification generic|supporting \
        --consumer features.<feature>[.<subdomain>] [--consumer ...] [--settings]
    python3 -m bin.new_package umbrella <name> --area <area>
    python3 -m bin.new_package subdomain <umbrella>.<name> --area <area> [--settings]
    python3 -m bin.new_package core|common <umbrella> [--settings]
    python3 -m bin.new_package promote <feature> --subdomain <name>
"""

import argparse
import keyword
import re
import shutil
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from string import Template
from typing import Any

from bin.freeze_guard import EXCLUDED_DIR_NAMES, iter_python_files
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
    rename_enablement_key,
    rename_entry_point,
    rename_in_contracts,
    render,
    settings_table,
    umbrella_contract,
    umbrella_member,
)

APP_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = Path(__file__).resolve().parent / "package_templates"
FEATURES = "features"
CAPABILITIES = "capabilities"
KINDS = ("feature", "capability", "umbrella", "subdomain", "core", "common", "promote")
PLUGIN_KINDS = frozenset({"feature", "capability", "subdomain"})
AREA_KINDS = PLUGIN_KINDS | {"umbrella"}
UMBRELLA_MEMBER_KINDS: dict[str, UmbrellaMember] = {"subdomain": "subdomain", "core": "core", "common": "common"}
CLASSIFICATIONS = ("generic", "supporting")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
CONSUMER = re.compile(r"^features\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")
# A subdomain named like a layout-table directory or an umbrella kernel would be read as one.
COMMON = "common"
SHARED_AREA = "shared"
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
    subdomain: str | None = None


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
    parser.add_argument(
        "target", help="<name>; <umbrella>.<name> for a subdomain; <umbrella> for core or common; the feature to promote"
    )
    parser.add_argument("--area", help="product area: a [plugins.<area>] table in config/base.toml")
    parser.add_argument("--classification", help="capability only: generic or supporting")
    parser.add_argument("--consumer", action="append", default=[], help="capability only: features.<feature>[.<subdomain>]")
    parser.add_argument("--settings", action="store_true", help="add settings.py and its [<table>] in base.toml")
    parser.add_argument("--subdomain", help="promote only: the subdomain the flat feature's code becomes")
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
        subdomain=args.subdomain,
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
    """The settings table: the module path joined by ``_`` (configuration.md); an umbrella's common/ reads [<umbrella>]."""
    if package.name == COMMON and package.umbrella:
        return package.umbrella
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


def _capability_area(request: Request, pyproject: dict[str, Any], base: dict[str, Any]) -> str:
    """The area a capability's key goes in: its consumers' area, or shared when they span two or more (plugins.md)."""
    entry_points: dict[str, str] = pyproject["project"]["entry-points"].get("sre_bot", {})
    area_of = {name: area for area, keys in base.get("plugins", {}).items() for name in keys}
    areas = {
        area_of[name]
        for consumer in request.consumers
        for name, target in entry_points.items()
        if (target == consumer or target.startswith(f"{consumer}.")) and name in area_of
    }
    if len(areas) > 1:
        if SHARED_AREA not in plugin_areas(base):
            raise GeneratorError(
                f"the consumers sit in {' and '.join(sorted(areas))}: plugins.md puts this capability's key in "
                "[plugins.shared], which the first cross-area capability task builds (PluginsSettings.shared and the "
                "table, TASK-83.4 or TASK-122); build it first"
            )
        needed = SHARED_AREA
    elif areas:
        needed = areas.pop()
    elif request.area:
        return request.area
    else:
        raise GeneratorError("no consumer has an enablement key to take the area from; pass --area")
    if request.area and request.area != needed:
        raise GeneratorError(f"the consumers put this capability's key in [plugins.{needed}], not [plugins.{request.area}]")
    return needed


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
        "title": _title("_".join(package.module.split(".")[1:])),
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
            "README.md": "core_readme.md.tmpl",
            "api.py": "core_api.py.tmpl",
            "service.py": "service.py.tmpl",
            "interfaces.py": "interfaces.py.tmpl",
        },
        "common": {"__init__.py": "common_init.py.tmpl", "README.md": "common_readme.md.tmpl"},
    }[request.kind]
    if request.settings and request.kind != "umbrella":
        files = files | {"settings.py": "settings.py.tmpl"}
    return files


def _product_scope_line(request: Request, package: Package) -> str | None:
    if request.kind not in ("feature", "capability", "umbrella") or request.area in (None, SHARED_AREA):
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
    if request.kind == "promote":
        return promote(request)
    package = _locate(request)
    pyproject_path = request.root / "pyproject.toml"
    base_path = request.root / "config" / "base.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    base_text = base_path.read_text(encoding="utf-8")
    base = tomllib.loads(base_text)
    if request.kind == "capability":
        _check_capability(request)
        request = replace(request, area=_capability_area(request, tomllib.loads(pyproject_text), base))
    if request.kind in AREA_KINDS and not request.area:
        raise GeneratorError(f"--area is required for a {request.kind}")
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
            "When register_requirements declares a requirement, switch the plugin off in config/ci.toml "
            "(CI configures no vendor; a guard test fails otherwise, plugins.md).",
        ]
    scope_line = _product_scope_line(request, package)
    if scope_line:
        lines.append(f"decisions/product-scope.md, add to the table: {scope_line}")
    if request.settings:
        lines.append(
            f"settings.py reads [{_table(package)}] in config/base.toml; add its keys to both. When a plugin requires "
            "one of its keys, build the slice in server/configuration/host_configuration.py (plugins.md 2026-11-05)."
        )
    lines.append(
        f"Next: write the README, declare requirements, add tests under tests/unit/{_template_values(request, package)['test_path']}/; "
        "then make check-package-shape check-import-contracts check-settings-key-ownership."
    )
    return lines


def _module_renamer(feature: str, subdomain: str, settings_moved: bool) -> Callable[[str], str]:
    """Rewrite references to a promoted feature: its modules move into the subdomain, settings into common/."""
    pattern = re.compile(rf"\b{FEATURES}\.{feature}\b(?:\.(\w+))?")

    def replace(match: re.Match[str]) -> str:
        tail = match.group(1)
        if tail is None:
            return f"{FEATURES}.{feature}.{subdomain}"
        if tail == "settings" and settings_moved:
            return f"{FEATURES}.{feature}.common.settings"
        return f"{FEATURES}.{feature}.{subdomain}.{tail}"

    return lambda text: pattern.sub(replace, text)


def _render_configs(root: Path, edits_for: Callable[[dict[str, Any]], list[Edit]]) -> dict[Path, str]:
    """The configuration files whose [plugins.*] tables change, rendered and verified."""
    rendered: dict[Path, str] = {}
    for path in sorted((root / "config").glob("*.toml")):
        text = path.read_text(encoding="utf-8")
        edits = edits_for(tomllib.loads(text))
        if edits:
            rendered[path] = render(text, edits)
    return rendered


def promote(request: Request) -> list[str]:
    """Turn a flat plugin feature into an umbrella whose first subdomain holds its code.

    feature-packages.md: a feature too large for one service becomes an umbrella, keeping
    its name. Its modules move into ``<feature>/<subdomain>/``, settings.py into
    ``common/`` (keeping its table and environment names), every ``features.<feature>``
    reference in the app's Python is rewritten, the entry point and the enablement key in
    every configuration file are renamed ``<feature>.<subdomain>``, and the umbrella gets
    its layers contract. Everything is computed and verified before anything moves.
    """
    root, feature, subdomain = request.root, request.target, request.subdomain
    _check_name(feature)
    directory = root / FEATURES / feature
    if not directory.is_dir():
        raise GeneratorError(f"no feature '{feature}' under features/")
    if not subdomain:
        raise GeneratorError("promote needs --subdomain <name>: the subdomain the feature's code becomes")
    _check_name(subdomain)
    if subdomain in RESERVED_SUBDOMAINS:
        raise GeneratorError(f"'{subdomain}' is reserved for an umbrella kernel or a layout-table directory")

    pyproject_path = root / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    old_module = f"{FEATURES}.{feature}"
    target = pyproject["project"]["entry-points"].get("sre_bot", {}).get(feature, "")
    if target not in (old_module, f"{old_module}.plugin"):
        raise GeneratorError(f"'{feature}' is not a flat plugin named by an entry point; only one can be promoted")

    settings_moved = (directory / "settings.py").is_file()
    rename = _module_renamer(feature, subdomain, settings_moved)
    new_name = f"{feature}.{subdomain}"
    try:
        edits: list[Edit] = rename_entry_point(pyproject, feature, new_name, rename(target))
        edits += rename_in_contracts(pyproject, rename, keep=frozenset({"feature-independence"}))
        edits += umbrella_contract(pyproject, feature)
        new_pyproject = render(pyproject_text, edits)
        for member, kind in [(subdomain, "subdomain"), *([("common", "common")] if settings_moved else [])]:
            member_kind = UMBRELLA_MEMBER_KINDS[kind]
            new_pyproject = render(new_pyproject, umbrella_member(tomllib.loads(new_pyproject), feature, member, member_kind))
        configs = _render_configs(root, lambda config: rename_enablement_key(config, feature, new_name))
    except (TomlEditError, tomllib.TOMLDecodeError) as error:
        raise GeneratorError(str(error)) from error

    moves = {
        child: (root / FEATURES / feature / "common" / child.name)
        if child.name == "settings.py"
        else directory / subdomain / child.name
        for child in sorted(directory.iterdir())
        if child.name not in EXCLUDED_DIR_NAMES
    }
    rewrites: dict[Path, str] = {}
    for path in [*iter_python_files(root), *sorted(directory.rglob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        if rename(text) != text:
            moved = next((new / path.relative_to(old) for old, new in moves.items() if path.is_relative_to(old)), path)
            rewrites[moved] = rename(text)
    values = {"title": _title(feature), "umbrella": old_module}

    shutil.rmtree(directory / "__pycache__", ignore_errors=True)
    for old, new in moves.items():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
    (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / "README.md").write_text(_template("umbrella_readme.md.tmpl", values), encoding="utf-8")
    if settings_moved:
        common_values = {**values, "title": _title(f"{feature}_common")}
        (directory / "common" / "__init__.py").write_text(_template("common_init.py.tmpl", common_values), encoding="utf-8")
        (directory / "common" / "README.md").write_text(_template("common_readme.md.tmpl", common_values), encoding="utf-8")
    for path, text in rewrites.items():
        path.write_text(text, encoding="utf-8")
    pyproject_path.write_text(new_pyproject, encoding="utf-8")
    for path, text in configs.items():
        path.write_text(text, encoding="utf-8")

    lines = [
        f"Promoted {old_module} to an umbrella: its code is now {old_module}.{subdomain}"
        + (", its settings.py is common/settings.py (same table and environment names)." if settings_moved else "."),
        f"Entry point and enablement key renamed '{feature}' -> '{new_name}' in pyproject.toml and "
        + ", ".join(f"config/{path.name}" for path in configs)
        + f"; {len(rewrites)} file(s) rewritten.",
        f"Run 'uv sync' so the renamed entry point is installed. Rename any PLUGINS__<AREA> override of '{feature}' in app/.env.",
        f"Next: move tests/*/features/{feature}/ tests under {subdomain}/ if they test it, grep the docs for "
        f"'{old_module}', then make check-package-shape check-import-contracts check-settings-key-ownership.",
    ]
    return lines


def _template(name: str, values: dict[str, str]) -> str:
    return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(values)


def _ask(prompt: str) -> str:
    return input(f"{prompt}: ").strip()


def prompt_arguments() -> list[str]:
    """Ask for each value on a terminal; return them as command-line arguments."""
    kind = _ask(f"Kind ({' / '.join(KINDS)})")
    hints = {"subdomain": "<umbrella>.<subdomain>", "core": "umbrella", "common": "umbrella", "promote": "flat feature"}
    argv = [kind, _ask(f"Name ({hints.get(kind, 'lower snake_case')})")]
    if kind in AREA_KINDS:
        base = tomllib.loads((APP_ROOT / "config" / "base.toml").read_text(encoding="utf-8"))
        argv += ["--area", _ask(f"Product area ({' / '.join(plugin_areas(base))})")]
    if kind == "capability":
        argv += ["--classification", _ask(f"Classification ({' / '.join(CLASSIFICATIONS)})")]
        for consumer in _ask("Feature consumers (features.<feature>[.<subdomain>], comma-separated)").split(","):
            argv += ["--consumer", consumer.strip()]
    if kind == "promote":
        return [*argv, "--subdomain", _ask("Subdomain the feature's code becomes")]
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
