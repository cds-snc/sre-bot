"""Service-scope contract: how non-HTTP entry points resolve core services."""

from contracts.services.scope import ServiceResolver, ServiceScopeOpener

__all__ = ["ServiceResolver", "ServiceScopeOpener"]
