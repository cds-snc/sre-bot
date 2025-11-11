Group Provider Implementation
=============================

This package provides a framework for implementing group providers that interact with identity management systems. Providers follow a standardized contract for managing group memberships across different directory services.

Quick Links
-----------

- **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** — Complete guide for implementing new providers, including architecture, required methods, patterns, and examples.
- **base.py** — Full provider contract documentation and base classes
- **google_workspace.py** — Reference implementation for Google Workspace
- **aws_identity_center.py** — Reference implementation for AWS Identity Center

Requirements for New Providers
------------------------------

Providers must subclass `GroupProvider` or `PrimaryGroupProvider` from `modules.groups.providers.base` and follow these rules:

- Constructible without reading global config via:
  1. A no-argument `__init__()` that sets sensible defaults, or
  2. A no-argument classmethod `from_config()` or `from_empty_config()` that returns a provider instance
- Expose `capabilities` (a `ProviderCapabilities` instance) to communicate features like `is_primary`
- Implement all abstract methods defined by the base class
- Implement `classify_error()` to handle provider-specific API errors
- Implement `_health_check_impl()` for lightweight connectivity checks

Provider Activation
-------------------

The framework automatically discovers and activates providers:

- `load_providers()` imports all provider modules under this package (called by app startup)
- `activate_providers()` instantiates discovered providers and applies configuration overrides from `settings.groups.providers.*`
- Primary provider selection (automatic):
  1. If exactly one active provider sets `capabilities.is_primary == True`, it becomes primary
  2. If only one provider is active, it becomes primary
  3. Otherwise activation fails and requires an explicit primary provider configuration

Key Framework Features
----------------------

- **Email-Based Operations**: Write operations accept email addresses as universal member identifiers
- **Circuit Breaker Protection**: All provider operations are wrapped with circuit breaker protection to prevent cascading failures
- **Unified Error Handling**: Providers classify errors via `classify_error()` to enable intelligent retry logic
- **Email Validation**: Centralized `validate_member_email()` function with RFC 5321/5322 compliance
- **Provider Operation Decorator**: `@provider_operation` decorator handles error classification and response wrapping
- **Normalization**: Providers convert provider-specific schemas to canonical `NormalizedMember` and `NormalizedGroup` models
- **Health Checks**: Built-in health check operations for monitoring provider connectivity

Getting Started
---------------

See [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) for:

- Step-by-step implementation instructions
- Complete provider contract specification
- Code examples and patterns
- Email validation and error classification
- Testing strategies
- Configuration options
