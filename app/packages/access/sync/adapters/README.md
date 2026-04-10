# Access Sync Adapters

Platform adapters translate generic Access Sync operations (`provision_user`, `apply_entitlement`, …) into real API calls for a specific identity platform. Each adapter is registered in `packages/access/sync/registry.py` and selected at runtime by matching the `platform` key in the sync config.

---

## Available Adapters

| Adapter class | Module | Platform key | Notes |
|---|---|---|---|
| `AwsIdentityCenterAdapter` | `aws_identity_center.py` | `aws` | Group membership via AWS IdentityStore |
| `FakePlatformAdapter` | `fake_platform.py` | `fake` | In-memory deterministic adapter for local dev and tests |

---

## AWS Identity Center Adapter (`AwsIdentityCenterAdapter`)

### What it does

Maps IDP security-group slugs to AWS Identity Center groups via **IdentityStore group membership**. When a user gains or loses membership in an IDP group that corresponds to an AWS IC group, the adapter creates or deletes the corresponding `GroupMembership` record.

v1 entitlement model: **group membership only**. Direct user-to-account permission-set assignments are deferred to a future feature.

### Capabilities

| Capability | Supported | Notes |
|---|---|---|
| `provision_user` (ensure_user) | ✅ | Creates user in IdentityStore with email-derived name if absent |
| `disable_user` | ❌ | AWS IC has no native disable state; returns `UNSUPPORTED_OPERATION` |
| `remove_user` | ✅ | Deletes user from IdentityStore (idempotent) |
| `apply_entitlement` | ✅ | Adds user to IC group via `CreateGroupMembership` (idempotent) |
| `remove_entitlement` | ✅ | Removes user from IC group (idempotent, no-op if already absent) |
| `fetch_current_state` | ✅ | Lists all IC group memberships for a user |
| Bulk user delta | ✅ | Batch membership reads supported |
| Multiple entitlement types | ❌ | Only `"group"` supported in v1 |

### Entitlement ID format

Entitlement IDs are **AWS IdentityStore GroupIds** (UUIDs):

```
a1b2c3d4-1234-5678-abcd-ef0123456789
```

The adapter resolves display-name tokens (e.g. `finops-readonly`) to GroupId UUIDs at sync time using an in-memory `_AwsGroupIndex` built from a single `ListGroups` call. Resolution priority:

1. UUID-shaped input → verified via `DescribeGroup`, used as-is
2. Exact display-name match (case-sensitive)
3. Normalized (casefold) display-name match — only if unambiguous

If multiple groups normalize to the same token, the adapter returns `AMBIGUOUS_GROUP_NAME` (permanent error, no retry).

### Infrastructure requirements

| Requirement | Detail |
|---|---|
| `AWS_SSO_INSTANCE_ID` | Bootstrap setting consumed by `AWSClients`; the adapter reads it from the pre-configured client |
| IAM permissions | `identitystore:ListUsers`, `identitystore:CreateUser`, `identitystore:DeleteUser`, `identitystore:ListGroups`, `identitystore:ListGroupMembershipsForMember`, `identitystore:CreateGroupMembership`, `identitystore:DeleteGroupMembership` |
| `AWSClients` | Injected from `infrastructure.services`; never instantiated in the adapter directly |

The adapter does **not** read settings directly. Configuration is consumed by `AWSClients` at the infrastructure layer before the adapter is constructed.

### Platform policy fields that matter for this adapter

Because `disable_user` is unsupported, the `authn_removal_mode` field must be set to `"delete"` for AWS:

```json
{
  "platforms": {
    "aws": {
      "authn_token": "authn",
      "authn_removal_mode": "delete"
    }
  }
}
```

Setting `authn_removal_mode` to `"disable"` will cause every authn-group removal to return `UNSUPPORTED_OPERATION` and the sync run will be flagged as requiring manual action.

See [../../README.md](../../README.md) for the full `PlatformPolicy` field reference and how to configure `mode_overrides`.

### User provisioning

When creating a new user, the adapter derives a display name from the email local part:

- `alice.smith@example.com` → GivenName=`Alice`, FamilyName=`Smith`
- `alice@example.com` → GivenName=`Alice`, FamilyName=`(empty)`

The user is created with `UserName` set to the full email address, which serves as the stable lookup key across all subsequent IdentityStore calls.

---

## Fake Platform Adapter (`FakePlatformAdapter`)

An in-memory adapter used for **local development and automated tests**. It holds a small set of pre-seeded users and group memberships and supports all operations including `disable_user`.

Use the `fake` platform key in your local runtime config to exercise the full sync orchestration path without AWS credentials:

```json
{
  "platforms": {
    "fake": {
      "authn_token": "authn",
      "authn_removal_mode": "disable"
    }
  }
}
```

Pre-seeded state:

| Entity | Value |
|---|---|
| Users | `alice@example.com`, `bob@example.com`, `carol@example.com` |
| Group `fake-group-admin` | `alice`, `carol` |
| Group `fake-group-read` | `bob` |

---

## Writing a new adapter

1. Create `packages/access/sync/adapters/<platform_name>.py`.
2. Implement the methods called by `SyncOrchestrator`: `capabilities()`, `get_user()`, `ensure_user()`, `disable_user()`, `remove_user()`, `apply_entitlement()`, `remove_entitlement()`, `fetch_current_state()`, `get_current_entitlement_ids()`.
3. Return `OperationResult` from every method — never raise.
4. Register the adapter in `packages/access/sync/registry.py`.
5. Add a platform policy entry that matches the new platform key.
