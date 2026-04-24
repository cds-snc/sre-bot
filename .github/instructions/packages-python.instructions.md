---
name: Packages Python Rules
description: Use for package-layer Python work under app/packages; enforces boundaries, registration, and type model selection.
applyTo: app/packages/**/*.py
---

- Keep business logic in package services and avoid infrastructure leakage.
- Ensure package behavior is plugin-registerable and startup-initialized.
- Prefer Protocol plus frozen dataclass internal boundaries; use BaseModel only at untrusted I/O boundaries.
- For new package settings, define package-local settings modules and avoid expanding central settings aggregators.
- Keep route handlers thin and delegate business behavior to package services.
