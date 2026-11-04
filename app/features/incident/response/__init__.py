"""Incident response subdomain: declare, status, roles and the rest of the live incident (decisions/incident-management.md).

Holds its settings and the plugin module (``plugin.py``, the entry point), which registers
the incident legacy upgrade job, until the rebuild (TASK-145.7) moves the behaviour in from
modules/incident. ``settings.py`` stays importable by the host and the legacy modules.
"""
