---
adr_id: ADR-0041
title: "OpenAPI Documentation Standards"
status: Accepted
decision_type: Feature
tier: Tier-4
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0033
related_packages: []
review_state: stale
---
# OpenAPI Documentation Standards

**Status**: ACCEPTED — April 2026  
**Tier**: 4 — Application

---

## Context

FastAPI auto-generates an OpenAPI schema from route declarations. Without consistent standards, the generated docs are incomplete, inconsistent, and unhelpful for consumers (internal tooling, Backstage, partner integrations).

---

## Decision

All route handlers must declare a minimum set of OpenAPI metadata. The standards below are enforced via code review.

---

## Required Metadata Per Route

```python
from fastapi import APIRouter, HTTPException, status
from packages.feature.schemas import FeatureRequest, FeatureResponse

router = APIRouter(prefix="/feature", tags=["Feature"])

@router.post(
    "/actions",
    summary="Perform a feature action",               # ✅ Short imperative phrase (≤ 8 words)
    description=(
        "Performs the requested action on the feature target. "
        "Returns the updated state on success."
    ),                                                # ✅ 1-2 sentence description of behaviour
    response_model=FeatureResponse,                   # ✅ Always declared
    status_code=status.HTTP_200_OK,                   # ✅ Explicit success code
    responses={                                       # ✅ Document all non-200 responses
        400: {"description": "Invalid request parameters"},
        403: {"description": "Not authorised to perform this action"},
        404: {"description": "Target resource not found"},
        503: {"description": "Upstream service temporarily unavailable"},
    },
)
def action_endpoint(request: FeatureRequest) -> FeatureResponse:
    ...
```

---

## Router-Level Tags

Every `APIRouter` must declare exactly one `tags` entry. Tags group endpoints in the Swagger UI sidebar.

```python
# ✅ CORRECT — one tag, title-case
router = APIRouter(prefix="/groups", tags=["Groups"])

# ❌ WRONG — no tags
router = APIRouter(prefix="/groups")

# ❌ WRONG — multiple tags (fragmented sidebar)
router = APIRouter(prefix="/groups", tags=["Groups", "Directory"])
```

Tag names must match the feature package name, title-cased.

---

## Schema Field Documentation

Pydantic models used as request or response schemas must include `description` on every public field:

```python
from pydantic import BaseModel, Field

class AddMemberRequest(BaseModel):
    group_id: str = Field(..., description="Canonical group identifier (e.g. 'eng-oncall').")
    member_email: str = Field(..., description="Email address of the member to add.")
    dry_run: bool = Field(
        default=False,
        description="When true, validates the request without making changes.",
    )
```

---

## Deprecation

Mark deprecated endpoints with `deprecated=True`. Do not remove endpoints without at least one release cycle of deprecation.

```python
@router.get(
    "/legacy-endpoint",
    deprecated=True,
    summary="[Deprecated] Use /new-endpoint instead",
)
def legacy_endpoint():
    ...
```

---

## Operation IDs

FastAPI auto-generates `operationId` from the function name. Keep function names descriptive and unique across the application — they become the SDK method names for generated clients.

```python
# ✅ operationId: "add_group_member_groups_members_post"
@router.post("/members")
def add_group_member(...): ...

# ❌ operationId: "create_groups_post" — too generic
@router.post("/")
def create(...): ...
```

---

## Exclusions

Some internal or infrastructure routes should be excluded from the public schema:

```python
# api/routes/health.py — exclude internal probe from docs
@router.get("/healthz", include_in_schema=False)
def health_check():
    return {"status": "ok"}
```

Exclude:
- Internal liveness / readiness probes
- Debug or admin endpoints not intended for external consumers
- Webhook receiver endpoints (document separately in `README` or Runbook)

---

## Rules

- ✅ Every route handler declares `summary`, `response_model`, `status_code`, and `responses`
- ✅ Every `APIRouter` declares exactly one `tags` entry
- ✅ All Pydantic request/response fields include `description`
- ✅ Deprecated endpoints use `deprecated=True` before removal
- ✅ Function names are descriptive and unique across the application
- ✅ Internal probe and webhook endpoints use `include_in_schema=False`
- ❌ Do not leave `summary` as the default (function name with underscores)
- ❌ Do not use `Any` or `dict` as `response_model` — define an explicit schema
