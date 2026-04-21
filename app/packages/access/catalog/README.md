# Access Catalog

Read-only discovery layer that lets callers browse configured platforms and their available entitlements, annotated with the requesting user's current membership status.

---

## What it does

| Method | Route | Description |
|---|---|---|
| `list_platforms()` | `GET /api/v1/access/catalog` | Lists every platform defined in runtime config |
| `list_entitlements(platform, user_email)` | `GET /api/v1/access/catalog/{platform}` | Lists entitlements for a platform; annotated with `already_provisioned` per user |

Both endpoints are read-only — no IDP writes occur here.

---

## How entitlements are discovered

1. The service calls `directory.get_groups_for_prefix(prefix)` using the IDP group naming prefix from runtime config (e.g. `sg-aws-`).
2. Each discovered group slug is stripped of its platform prefix to extract the **entitlement token** (e.g. `sg-aws-scratch` → `scratch`).
3. The entitlement mode (`sync_managed`, `ephemeral`, `deactivated`) is resolved from `PlatformPolicy.mode_overrides` in runtime config. Any token without an override is `sync_managed` by default.
4. An optional `already_provisioned` flag is set by calling `directory.check_membership(group_email, user_email)`.

`requestable` is `true` when `mode == "sync_managed"` — only those entitlements can go through the access request flow.

---

## Token parsing (AWS)

For the `aws` platform, entitlement tokens are further decomposed using `AwsCatalogSlugParser` according to the naming convention:

```
Product(-Env)?-Role(-Service)?(-Resource)?
```

Example: `platform-prod-admin` → `product=platform`, `env=prod`, `role=admin`

The `known_envs` set controls which segments are treated as environment qualifiers. It is configured in the `catalog` extension block of your runtime config JSON:

```json
{
  "dir_prefix": "sg",
  "dir_separator": "-",
  "platforms": {
    "aws": { "authn_token": "authn", "authn_removal_mode": "delete" }
  },
  "extensions": {
    "catalog": {
      "parsers": {
        "aws": { "known_envs": ["dev", "staging", "prod"] }
      },
      "platform_display_names": {
        "aws": "AWS"
      }
    }
  }
}
```

Platforms without a registered parser fall back to `FallbackCatalogSlugParser`, which returns the raw token unparsed (`parsed=false`).

---

## Feature flag

```
ACCESS_CATALOG_ENABLED=true
```

The feature is disabled by default (`ACCESS_CATALOG_ENABLED=false`). All routes return `503` when disabled.

The flag maps to `settings.catalog.enabled` in `AccessSettings` (defined in `packages/access/common/settings.py`).

---

## Module map

| File | Purpose |
|---|---|
| `domain.py` | Internal dataclasses: `EntitlementEntry`, `PlatformSummary`, `ParsedEntitlementToken` |
| `schemas.py` | Pydantic HTTP response models |
| `service.py` | Orchestration — `list_platforms()` and `list_entitlements()` |
| `parsers.py` | `CatalogSlugParser` Protocol and `AwsCatalogSlugParser` implementation |
| `providers.py` | `get_catalog_settings()` — thin slice provider returning `AccessCatalogSettings` |
| `transport/routes.py` | FastAPI route handlers |
