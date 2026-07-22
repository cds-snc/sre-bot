---
name: testing-standards
description: Apply project testing standards for app/tests layout, naming, dependency overrides, and route/service coverage.
---

# Testing Standards

## Test Layout & Naming

Mirror `app/` under `app/tests/`:
- `app/tests/unit/` — isolated units with Protocol fakes. Cost <50ms.
- `app/tests/integration/` — feature + infrastructure with external deps stubbed. Cost <500ms.
- `app/tests/smoke/` — live systems. On-demand only.

Names: `test_<domain>_<entity>_<action>.py`. No generic names.

## Unit Tests

Test one function/class in isolation.

```python
async def test_item_service_fetch_success(mocker):
    fake_adapter = mocker.Mock(spec=ItemAdapter)
    fake_adapter.get_item.return_value = OperationResult(SUCCESS, payload=Item(...))
    
    service = ItemService(adapter=fake_adapter)
    result = await service.fetch("id1")
    
    assert result.status == SUCCESS
    assert result.payload.name == "expected"
```

Use Protocol-conformant fakes. Assert on OperationResult status, not provider details.

## Integration Tests

Test feature service + infrastructure with external deps stubbed.

```python
async def test_item_route_success(app, monkeypatch):
    fake_adapter = FakeItemAdapter()
    app.dependency_overrides[get_item_service] = lambda: ItemService(fake_adapter)
    
    client = TestClient(app)
    response = client.get("/items/id1")
    
    assert response.status_code == 200
    assert response.json()["name"] == "expected"
    
    app.dependency_overrides.clear()
```

Clear `dependency_overrides` in finally or use fixture autouse.

## Route Tests

1. Success: status code + response schema.
2. Failure paths: OperationResult → HTTP status + RFC 9457 body.
3. Auth/permission branches.

## Fixtures

Narrow-slice settings only. Clear `@lru_cache` between tests:

```python
@pytest.fixture(autouse=True)
def _clear_caches():
    yield
    from app.packages.myfeature import providers
    providers.get_service.cache_clear()
```

## Anti-patterns

- Tests outside `app/tests/`.
- Status-code-only assertions.
- Missing `dependency_overrides` cleanup.
- Full Settings objects in fixtures.
- Docstrings that reference external documents, task/ticket identifiers, sprint labels, plan step numbers, implementation phases, or transitory states (e.g. "before implementation", "AC#2 of TASK-X", "Step 1 of the plan"). Docstrings must describe behavior, stub strategy, and assertion rationale — nothing that becomes inaccurate as the project evolves.
