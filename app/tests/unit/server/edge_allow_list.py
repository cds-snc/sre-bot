"""WAF allow-list semantics and the route-table checks the edge tests share.

The AuthorizedEndpoints rule in terraform/waf.tf blocks every request whose path matches no
entry of terraform/authorized_endpoints.json: a byte match on the URI path with no text
transformation, so matching is case-sensitive and undecoded. A mounted route counts as allowed
only when every concrete path it serves passes: EXACTLY needs a template with no path
parameter, and STARTS_WITH compares the template's literal head (the text before the first
parameter). Any other positional constraint raises, so the check fails closed until a new
constraint is modelled on purpose.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
ALLOW_LIST_FILE = REPO_ROOT / "terraform" / "authorized_endpoints.json"
SUPPORTED_CONSTRAINTS = frozenset({"EXACTLY", "STARTS_WITH"})
CHECKED_ROUTE_KINDS = frozenset({"api", "route"})


@dataclass(frozen=True)
class EdgeEntry:
    path: str
    positional_constraint: str


@dataclass(frozen=True)
class MountedRoute:
    path: str
    methods: tuple[str, ...]
    kind: str
    authenticated: bool


def load_allow_list(file: Path = ALLOW_LIST_FILE) -> list[EdgeEntry]:
    return [EdgeEntry(item["path"], item["positional_constraint"]) for item in json.loads(file.read_text())]


def literal_head(template: str) -> str:
    return template.split("{", 1)[0]


def entry_allows(entry: EdgeEntry, template: str) -> bool:
    if entry.positional_constraint not in SUPPORTED_CONSTRAINTS:
        raise ValueError(f"unsupported positional_constraint {entry.positional_constraint!r} for {entry.path!r}")
    if entry.positional_constraint == "EXACTLY":
        return "{" not in template and template == entry.path
    return literal_head(template).startswith(entry.path)


def is_allowed(template: str, entries: Iterable[EdgeEntry]) -> bool:
    return any(entry_allows(entry, template) for entry in entries)


def _label(route: MountedRoute) -> str:
    return f"{','.join(route.methods) or '-'} {route.path}"


def edge_violations(
    routes: Iterable[MountedRoute],
    entries: list[EdgeEntry],
    internal: Mapping[str, str],
    alb_served: Mapping[str, str],
) -> list[str]:
    """Return one message per disagreement between the mounted routes and the edge allow-list."""
    routes = list(routes)
    problems: list[str] = []
    for route in routes:
        if route.kind not in CHECKED_ROUTE_KINDS:
            problems.append(f"{_label(route)}: route type {route.kind} is not modelled by the edge check")
            continue
        allowed = is_allowed(route.path, entries)
        if allowed and route.path in internal:
            problems.append(
                f"{_label(route)} is listed intentionally internal but the edge allows it: fix {ALLOW_LIST_FILE.name} or the list"
            )
        if not allowed and route.path not in internal:
            problems.append(
                f"{_label(route)} is blocked at the edge: add an entry to terraform/{ALLOW_LIST_FILE.name} "
                "or list it as intentionally internal with a reason"
            )
    mounted = {route.path for route in routes}
    problems.extend(
        f"intentionally internal {path} is not a mounted route: remove it" for path in internal if path not in mounted
    )
    for entry in entries:
        if entry.path in alb_served:
            continue
        if not any(entry_allows(entry, path) for path in mounted):
            problems.append(f"allow-list entry {entry.positional_constraint} {entry.path} matches no mounted route: remove it")
    return problems


def authentication_violations(routes: Iterable[MountedRoute], prefix: str, public: Mapping[str, str]) -> list[str]:
    """Return one message per route under ``prefix`` that skips get_current_user without a recorded decision."""
    routes = [route for route in routes if route.path.startswith(prefix)]
    problems = [
        f"{_label(route)} has no get_current_user dependency: authenticate it or record it as public by decision"
        for route in routes
        if not route.authenticated and route.path not in public
    ]
    mounted = {route.path for route in routes}
    problems.extend(
        f"public-by-decision {path} is not a mounted route under {prefix}: remove it" for path in public if path not in mounted
    )
    return problems
