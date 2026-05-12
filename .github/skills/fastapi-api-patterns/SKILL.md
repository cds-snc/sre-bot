---
name: fastapi-api-patterns
description: Apply typed FastAPI route patterns with clean dependency boundaries, stable error mapping, and test coverage for success/failure paths.
---

## Handler Implementation

Routes parse input → call service → map OperationResult to HTTP.

```python
@router.get("/{id}", response_model=MyResponse)
async def get_item(
    item_id: str,
    service: Annotated[ItemService, Depends(get_item_service)]
) -> MyResponse:
    result = await service.fetch(item_id)
    return map_result(result, MyResponse)
```

Never import concrete implementations. Inject via `Annotated[Protocol, Depends(...)]` only.

## OperationResult → HTTP Mapping

| Status | HTTP | Body type |
|--------|------|-----------|
| SUCCESS | 200/201/202/204 | application/json (response_model) |
| NOT_FOUND | 404 | RFC 9457 problem+json |
| UNAUTHORIZED | 401/403 | RFC 9457 problem+json |
| PERMANENT_ERROR | 400/409/422 | RFC 9457 problem+json |
| TRANSIENT_ERROR | 503 + Retry-After | RFC 9457 problem+json |

RFC 9457 body includes: `type`, `status`, `title`, `detail`, `error_code`, `request_id`, `retry_after` (transient only).

Exhaustive mapping — no unmapped statuses.

## Forbidden

- Business logic in handlers.
- Concrete implementation imports.
- Returning raw OperationResult from routes.
- Validator-level HTTP status codes.