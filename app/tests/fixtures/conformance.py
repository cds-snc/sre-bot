"""Helpers for conformance-suite enrollment tests.

A conformance suite runs one set of cases against every implementation of a
Protocol through a parametrized fixture. Its enrollment test compares the
fixture's implementations with the concrete production subclasses of the
Protocol, so an adapter or fake that explicitly subclasses the Protocol but was
never added to the fixture fails instead of going unexercised.

Only explicit subclasses are visible here, and only once their modules are
imported, so the suite's conftest imports every implementation at module level.
"""

import inspect

PRODUCTION_ROOTS = frozenset({"infrastructure", "capabilities"})


def concrete_production_subclasses(protocol: type) -> set[type]:
    """Return every concrete class under a production root that explicitly subclasses ``protocol``.

    Sub-Protocols and abstract intermediates are skipped; test doubles defined
    under ``tests`` are outside the production roots and never count.
    """
    found: set[type] = set()
    pending = list(protocol.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        if getattr(cls, "_is_protocol", False) or inspect.isabstract(cls):
            continue
        if cls.__module__.partition(".")[0] in PRODUCTION_ROOTS:
            found.add(cls)
    return found
