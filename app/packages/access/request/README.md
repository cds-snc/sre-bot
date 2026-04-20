# Access Requests

Manages the full lifecycle of user access requests: submission, approval, rejection, cancellation, and retry.

---

## How it works

1. User submits a request with `platform` and `group_slug` (e.g. `sg-aws-scratch`).
2. The service resolves the group in the IDP and derives the `entitlement_id` token server-side (`scratch`).
3. Approver candidates are resolved from the group's owners, falling back to `sg-org-admins`.
4. On approval threshold met, the service writes the membership directly to the IDP (Google Workspace) — the source of truth.
5. An `access_request_approved` event is dispatched, triggering Access Sync to propagate the change to the external platform (e.g. AWS Identity Center).
6. When Access Sync completes, the request transitions to `completed` (or `failed`).

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/access/requests` | Submit a request |
| `POST` | `/api/v1/access/requests/{id}/approve` | Approve (approvers only) |
| `POST` | `/api/v1/access/requests/{id}/reject` | Reject (approvers only) |
| `POST` | `/api/v1/access/requests/{id}/cancel` | Cancel (requester only) |
| `POST` | `/api/v1/access/requests/{id}/retry` | Retry a failed IDP write (approvers only) |
| `GET` | `/api/v1/access/requests/{id}` | Get status + decision history |

### Submit body (minimal)

```json
{
  "platform": "aws",
  "group_slug": "sg-aws-scratch",
  "justification": "Need scratch access for incident response."
}
```

`entitlement_id` is **not** submitted by the caller. It is derived server-side by stripping the platform prefix from `group_slug` (`sg-aws-` → `scratch`).

Optional fields: `actor_type` (default `self`), `user_email` (required for `delegated`), `entitlement_type` (default `group`), `ticket_id`.

---

## State machine

```
submitted ──► pending_approval ──► approved ──► completed
                    │                  │
                    ▼                  ▼
                rejected            failed ──► (retry) ──► approved
                    │
                cancelled
```

Terminal states (no further transitions without operator action): `rejected`, `cancelled`, `completed`, `failed`.

`failed` is recoverable via `POST .../retry` by an authorized approver once the underlying infra issue is fixed (e.g. Google DWD scope not configured).

---

## Key design decisions

**IDP-first**: The IDP (Google Workspace) is written before the sync event is published. If the IDP write fails, the request moves to `failed` and no sync is triggered — preventing a diverged state where the platform has access but the IDP does not.

**`entitlement_id` derived, not submitted**: The token segment of the group slug (e.g. `scratch` from `sg-aws-scratch`) is derived server-side using the shared `AccessRuntimeConfig.group_prefix()`. This removes a redundant required field and prevents mismatches between `group_slug` and `entitlement_id`.

**Approvers snapshotted at submission**: `resolved_approvers` is captured from the IDP at submission time and stored on the request. Decisions are validated against this snapshot — a group membership change during the approval window does not retroactively affect who can approve.

---

## Module map

| File | Purpose |
|---|---|
| `domain.py` | Frozen dataclasses: `AccessRequest`, `ApprovalDecision`, `RequestAuditEvent` |
| `schemas.py` | Pydantic HTTP boundary models (request bodies / responses) |
| `service.py` | Lifecycle orchestration — the canonical place to understand the flow |
| `policies.py` | Pure policy functions: auto-approval, self-approval guard, approver resolution |
| `store.py` | DynamoDB repository (`sre_bot_access_requests` table) |
| `providers.py` | `@lru_cache` singletons — object graph wiring |
| `events.py` | Event name constants for this package |
| `transport/routes.py` | FastAPI route handlers — HTTP mapping only, no business logic |

---

## DynamoDB table: `sre_bot_access_requests`

| Key | Pattern | Used for |
|---|---|---|
| PK | `ACCESS_REQUEST#{request_id}` | All items for a request |
| SK | `REQUEST` | The request record |
| SK | `DECISION#{decided_at}#{actor_email}` | Approval/rejection decisions |
| SK | `AUDIT#{timestamp}#{event_type}` | Audit trail events |
