"""Plugin namespace constant and the pluggy markers bound to it.

The namespace comes from the installed project metadata, so the hookspec
marker, the hookimpl marker, the plugin manager and the entry-point group all
share one name. Importing this module where the project is not installed
raises ``PackageNotFoundError``.
"""

from importlib.metadata import metadata

import pluggy

PLUGIN_NAMESPACE = metadata("sre-bot")["Name"].replace("-", "_")

hookspec = pluggy.HookspecMarker(PLUGIN_NAMESPACE)
hookimpl = pluggy.HookimplMarker(PLUGIN_NAMESPACE)
