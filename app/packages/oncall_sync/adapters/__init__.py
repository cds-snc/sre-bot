"""Concrete adapters for the on-call sync feature.

Each adapter implements one of the protocols defined in ``ports.py`` by
wrapping a vendor SDK call. Adapters are vendor-aware; nothing else in
the package should import vendor SDKs directly.
"""
