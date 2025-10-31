Provider registration and activation (simplified)
===============================================

This package provides a simplified activation model for group providers.

Activation rules (developer-facing)

- Providers must subclass `GroupProvider` or `PrimaryGroupProvider` from
  `modules.groups.providers.base`.
- Providers should be constructible without reading global config. Prefer:
  1. a no-argument `__init__()` that sets sensible defaults, or
  2. a no-argument classmethod `from_config()` or `from_empty_config()` that
     returns a provider instance.
- Providers should expose `capabilities` (a `ProviderCapabilities` instance)
  to communicate `is_primary` and other features.
- Providers may expose `default_prefix` or a `prefix` property — the
  activation process will use that as the canonical prefix. Duplicate
  prefixes among active providers will fail activation.

Activation behavior

- `load_providers()` will import provider modules under this package.
  - App's main.py is expected to call this during startup.
- `activate_providers()` will instantiate discovered provider classes using
  the rules above. It no longer consults global `settings.groups.*` for
  per-provider overrides.
- Primary selection rules:
  1. If exactly one active provider sets `capabilities.is_primary == True`, it
     becomes primary.
  2. If only one provider is active, it becomes primary.
  3. Otherwise activation fails and asks for an explicit `is_primary` mark or
     a single-provider deployment.

