"""Throwaway installed distributions for plugin-loading tests.

A dist-info directory and its plugin modules are written under a temporary
directory. The returned ``PathDistribution`` exposes its entry points exactly
as an installed wheel does, so tests drive the real
``pm.load_setuptools_entrypoints`` without touching first-party metadata.
"""

from importlib.metadata import PathDistribution
from pathlib import Path


def write_plugin_dist(
    root: Path,
    group: str,
    entry_points: dict[str, str],
    modules: dict[str, str] | None = None,
) -> PathDistribution:
    """Write a fake dist-info declaring ``entry_points`` and the ``modules`` sources under ``root``.

    Args:
        root: Directory that will hold the dist-info and the module files; the
            caller puts it on ``sys.path`` so the modules import.
        group: Entry-point group the entry points are declared under.
        entry_points: Entry-point name to target module.
        modules: Module name to Python source, written as ``<name>.py``.

    Returns:
        The distribution, ready to stand in for ``importlib.metadata.distributions()``.
    """
    dist_info = root / "fake_plugins-0.0.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: fake-plugins\nVersion: 0.0.0\n")
    lines = [f"[{group}]", *(f"{name} = {target}" for name, target in entry_points.items())]
    (dist_info / "entry_points.txt").write_text("\n".join(lines) + "\n")
    for module_name, source in (modules or {}).items():
        (root / f"{module_name}.py").write_text(source)
    return PathDistribution(dist_info)
