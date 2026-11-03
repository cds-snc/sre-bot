"""Print every route the application can mount, with every installed plugin's routes included.

Run as a subprocess by test_server_edge_allow_list_routes: the inventory needs a fresh
interpreter, since plugin modules register their routers on import-free hookimpls but the
test process has already imported and patched parts of the tree. The app is built by the real
create_app on the ci configuration, then a new plugin manager loads every entry point of the
plugin namespace, enabled or not, and calls each register_routes hookimpl on that app. No
lifespan runs. The rows are printed on one line after a marker.
"""

import json
from collections.abc import Callable
from typing import Any

import pluggy
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import Route

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from infrastructure.security import get_current_user
from server.server import create_app

MARKER = "EDGE_ROUTE_ROWS="


def _calls(dependant: Dependant) -> set[Callable[..., Any]]:
    found: set[Callable[..., Any]] = set()
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            found.add(dependency.call)
        found |= _calls(dependency)
    return found


def main() -> None:
    app = create_app()
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)
    for plugin in pm.get_plugins():
        register = getattr(plugin, "register_routes", None)
        if register is not None:
            register(app=app)
    plugins = sorted(name for name, _ in pm.list_name_plugin())
    rows: list[dict[str, object]] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if isinstance(route, APIRoute):
            kind = "api"
            authenticated = get_current_user in _calls(context.dependant)
        elif type(route) is Route:
            kind = "route"
            authenticated = False
        else:
            kind = type(route).__name__
            authenticated = False
        rows.append(
            {"path": context.path, "methods": sorted(context.methods or []), "kind": kind, "authenticated": authenticated}
        )
    print(MARKER + json.dumps({"plugins": plugins, "routes": rows}))


if __name__ == "__main__":
    main()
