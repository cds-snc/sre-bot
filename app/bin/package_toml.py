"""The package generator's edits to pyproject.toml and config/base.toml.

decisions/feature-packages.md has a generator create every package; a new
package also needs its entry point, its import-linter contracts and its
enablement key (plugins.md). Each builder here reads the parsed file and returns
the edits that package needs, or none when they are already present, so running
the generator twice changes nothing. ``render`` applies the edits to a tomlkit
document, which keeps every comment and the file's layout, then ``verify``
re-reads the result with tomllib and requires it to equal the old data with the
same edits applied: anything else raises before a byte is written.
"""

import copy
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import tomlkit
from tomlkit.container import Container
from tomlkit.items import AoT, Table

ENTRY_POINT_GROUP = "sre_bot"
PROTECTED_PLUGINS = "protected-plugins"
FEATURE_INDEPENDENCE = "feature-independence"
# Every contract that lists features as a source lists capabilities too (plugin-architecture.md Checks).
CAPABILITY_GUARDED_CONTRACTS = ("no-host-imports", "integrations-via-adapters", "no-legacy-imports", "no-provider-imports")
SLACK_BOLT_CONTRACT = "slack-bolt-in-entrypoints"
CAPABILITY_SLACK_ENTRYPOINT = "capabilities.**.entrypoints.slack"
CAPABILITIES = "capabilities"
CORE = "core"
COMMON = "common"
SIBLING_SEPARATOR = " | "

type UmbrellaMember = Literal["subdomain", "core", "common"]


class TomlEditError(Exception):
    """An edit cannot be made, or its result is not exactly the intended change."""


@dataclass(frozen=True)
class Contract:
    """A path step selecting the import-linter contract table with this id."""

    id: str


type Step = str | Contract
type Location = tuple[Step, ...]


@dataclass(frozen=True)
class SetKey:
    """Set ``key`` to ``value`` in the table at ``path``."""

    path: Location
    key: str
    value: Any


@dataclass(frozen=True)
class Append:
    """Append ``value`` to the array (or array of tables) at ``path``."""

    path: Location
    value: Any


@dataclass(frozen=True)
class Insert:
    """Insert ``value`` at ``index`` in the array at ``path``."""

    path: Location
    index: int
    value: Any


@dataclass(frozen=True)
class Replace:
    """Replace the item at ``index`` in the array at ``path`` with ``value``."""

    path: Location
    index: int
    value: Any


@dataclass(frozen=True)
class DeleteKey:
    """Remove ``key`` from the table at ``path``."""

    path: Location
    key: str


type Edit = SetKey | DeleteKey | Append | Insert | Replace

CONTRACTS: Location = ("tool", "importlinter", "contracts")
ENTRY_POINTS: Location = ("project", "entry-points", ENTRY_POINT_GROUP)


def _contracts(pyproject: dict[str, Any]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = pyproject["tool"]["importlinter"]["contracts"]
    return contracts


def _contract(pyproject: dict[str, Any], contract_id: str) -> dict[str, Any]:
    for contract in _contracts(pyproject):
        if contract.get("id") == contract_id:
            return contract
    raise TomlEditError(f"pyproject.toml has no import-linter contract with id '{contract_id}'")


def _resolve(root: Any, path: Location) -> Any:
    node = root
    for step in path:
        node = next(item for item in node if item.get("id") == step.id) if isinstance(step, Contract) else node[step]
    return node


def apply(edits: Sequence[Edit], data: Any) -> None:
    """Apply ``edits`` in order to a tomlkit document or to plain parsed data."""
    for edit in edits:
        target = _resolve(data, edit.path)
        if isinstance(edit, DeleteKey):
            del target[edit.key]
            continue
        value = copy.deepcopy(edit.value)
        match edit:
            case SetKey():
                if isinstance(value, dict) and isinstance(target, Container | Table):
                    table = tomlkit.table()
                    table.update(value)
                    value = table
                target[edit.key] = value
            case Append():
                if isinstance(target, AoT) and len(target):
                    target[-1].add(tomlkit.nl())
                target.append(value)
            case Insert():
                target.insert(edit.index, value)
            case Replace():
                target[edit.index] = value


def verify(old_text: str, new_text: str, edits: Sequence[Edit]) -> None:
    """Raise unless ``new_text`` parses to the old data with exactly ``edits`` applied."""
    expected = tomllib.loads(old_text)
    apply(edits, expected)
    if tomllib.loads(new_text) != expected:
        raise TomlEditError("the edited TOML differs from the intended change; nothing was written")


def render(old_text: str, edits: Sequence[Edit]) -> str:
    """Return ``old_text`` with ``edits`` applied, comments and layout kept, after ``verify``."""
    document = tomlkit.parse(old_text)
    apply(edits, document)
    new_text = tomlkit.dumps(document)
    verify(old_text, new_text, edits)
    return new_text


def entry_point(pyproject: dict[str, Any], name: str, module: str) -> list[Edit]:
    """The entry-point line naming ``module`` as plugin ``name``."""
    group: dict[str, str] = pyproject["project"]["entry-points"][ENTRY_POINT_GROUP]
    if name in group:
        if group[name] == module:
            return []
        raise TomlEditError(f"entry point '{name}' already names '{group[name]}'")
    return [SetKey(ENTRY_POINTS, name, module)]


def protected_plugin(pyproject: dict[str, Any], module: str) -> list[Edit]:
    """The plugin module in the protected-plugins contract."""
    if module in _contract(pyproject, PROTECTED_PLUGINS)["protected_modules"]:
        return []
    return [Append((*CONTRACTS, Contract(PROTECTED_PLUGINS), "protected_modules"), module)]


def independent_feature(pyproject: dict[str, Any], module: str) -> list[Edit]:
    """The top-level feature in the feature-independence contract."""
    if module in _contract(pyproject, FEATURE_INDEPENDENCE)["modules"]:
        return []
    return [Append((*CONTRACTS, Contract(FEATURE_INDEPENDENCE), "modules"), module)]


def _umbrella_contract_id(pyproject: dict[str, Any], umbrella: str) -> str | None:
    container = f"features.{umbrella}"
    for contract in _contracts(pyproject):
        if contract.get("type") == "layers" and contract.get("containers") == [container]:
            contract_id = contract.get("id")
            if not isinstance(contract_id, str):
                raise TomlEditError(f"the layers contract over '{container}' has no id")
            return contract_id
    return None


def umbrella_contract(pyproject: dict[str, Any], umbrella: str) -> list[Edit]:
    """A new umbrella's exhaustive layers contract, with no layers until its members exist."""
    if _umbrella_contract_id(pyproject, umbrella) is not None:
        return []
    contract = {
        "id": f"{umbrella}-umbrella",
        "name": f"{umbrella} subdomains are independent siblings over core and common",
        "type": "layers",
        "containers": [f"features.{umbrella}"],
        "layers": [],
        "exhaustive": True,
    }
    return [Append(CONTRACTS, contract)]


def umbrella_member(pyproject: dict[str, Any], umbrella: str, member: str, kind: UmbrellaMember) -> list[Edit]:
    """``member`` in its umbrella's layers contract: subdomains as sorted siblings, over core, over common."""
    contract_id = _umbrella_contract_id(pyproject, umbrella)
    if contract_id is None:
        raise TomlEditError(f"no import-linter layers contract has containers = ['features.{umbrella}']")
    path: Location = (*CONTRACTS, Contract(contract_id), "layers")
    layers: list[str] = _contract(pyproject, contract_id)["layers"]
    sibling_lines = [index for index, layer in enumerate(layers) if layer not in (CORE, COMMON)]
    if len(sibling_lines) > 1:
        raise TomlEditError(f"contract '{contract_id}' has more than one subdomain layer: {layers}")

    if kind == "subdomain":
        if not sibling_lines:
            return [Insert(path, 0, member)]
        index = sibling_lines[0]
        siblings = set(layers[index].split(SIBLING_SEPARATOR))
        if member in siblings:
            return []
        return [Replace(path, index, SIBLING_SEPARATOR.join(sorted(siblings | {member})))]
    if member in layers:
        return []
    if kind == CORE:
        return [Insert(path, len(sibling_lines), CORE)]
    return [Append(path, COMMON)]


def capabilities_root(pyproject: dict[str, Any]) -> list[Edit]:
    """The first capability's bootstrap: the root package, the wheel package and the guarded source lists.

    The six-layer contract already names ``(capabilities)`` as an optional layer, so
    it matches once the package exists; contracts (b), (e), (g) and (k) start covering
    it here, and (j) lets its ``entrypoints/slack.py`` import slack_bolt
    (platform-entrypoints.md Checks).
    """
    edits: list[Edit] = []
    roots: list[str] = pyproject["tool"]["importlinter"]["root_packages"]
    if CAPABILITIES not in roots:
        edits.append(Append(("tool", "importlinter", "root_packages"), CAPABILITIES))
    wheel: list[str] = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    if CAPABILITIES not in wheel:
        index = sum(1 for package in wheel if package < CAPABILITIES)
        edits.append(Insert(("tool", "hatch", "build", "targets", "wheel", "packages"), index, CAPABILITIES))
    for contract_id in CAPABILITY_GUARDED_CONTRACTS:
        if CAPABILITIES not in _contract(pyproject, contract_id)["source_modules"]:
            edits.append(Append((*CONTRACTS, Contract(contract_id), "source_modules"), CAPABILITIES))
    if CAPABILITY_SLACK_ENTRYPOINT not in _contract(pyproject, SLACK_BOLT_CONTRACT)["allowed_importers"]:
        edits.append(Append((*CONTRACTS, Contract(SLACK_BOLT_CONTRACT), "allowed_importers"), CAPABILITY_SLACK_ENTRYPOINT))
    return edits


def plugin_areas(base: dict[str, Any]) -> list[str]:
    """The product areas that hold enablement keys: the tables under [plugins]."""
    return list(base.get("plugins", {}))


def enablement_key(base: dict[str, Any], area: str, name: str) -> list[Edit]:
    """Plugin ``name`` switched on in base.toml's [plugins.<area>] table."""
    areas = plugin_areas(base)
    if area not in areas:
        raise TomlEditError(f"no [plugins.{area}] table; choose one of: {', '.join(areas)}")
    for other in areas:
        if name in base["plugins"][other]:
            if other == area:
                return []
            raise TomlEditError(f"'{name}' already has an enablement key in [plugins.{other}]")
    return [SetKey(("plugins", area), name, True)]


def settings_table(base: dict[str, Any], table: str) -> list[Edit]:
    """An empty [<table>] for a new settings slice; the slice's keys are the author's to add."""
    if table in base:
        return []
    return [SetKey((), table, {})]


def rename_entry_point(pyproject: dict[str, Any], old_name: str, new_name: str, new_module: str) -> list[Edit]:
    """Plugin ``old_name`` re-registered as ``new_name`` naming ``new_module`` (a flat feature promoted)."""
    group: dict[str, str] = pyproject["project"]["entry-points"][ENTRY_POINT_GROUP]
    if old_name not in group:
        raise TomlEditError(f"no entry point named '{old_name}'")
    if new_name in group:
        raise TomlEditError(f"entry point '{new_name}' already names '{group[new_name]}'")
    return [DeleteKey(ENTRY_POINTS, old_name), SetKey(ENTRY_POINTS, new_name, new_module)]


def rename_in_contracts(pyproject: dict[str, Any], rename: Callable[[str], str], keep: frozenset[str]) -> list[Edit]:
    """Every string in every contract's string lists passed through ``rename``, except contracts with an id in ``keep``."""
    edits: list[Edit] = []
    for contract in _contracts(pyproject):
        contract_id = contract.get("id")
        if not isinstance(contract_id, str) or contract_id in keep:
            continue
        for key, values in contract.items():
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values):
                if isinstance(value, str) and rename(value) != value:
                    edits.append(Replace((*CONTRACTS, Contract(contract_id), key), index, rename(value)))
    return edits


def rename_enablement_key(config: dict[str, Any], old_name: str, new_name: str) -> list[Edit]:
    """Key ``old_name`` renamed ``new_name`` in whichever [plugins.<area>] table of a configuration file holds it."""
    for area, keys in config.get("plugins", {}).items():
        if old_name in keys:
            return [DeleteKey(("plugins", area), old_name), SetKey(("plugins", area), new_name, keys[old_name])]
    return []
