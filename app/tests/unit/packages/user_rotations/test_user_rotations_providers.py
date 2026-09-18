"""Unit tests for user-rotation service provider wiring."""

from collections.abc import Iterator

import pytest

from packages.user_rotations import providers

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _provider_cache_isolation() -> Iterator[None]:
    providers.get_user_rotations_service.cache_clear()
    yield
    providers.get_user_rotations_service.cache_clear()


def test_get_user_rotations_service_uses_configured_rotations(monkeypatch: pytest.MonkeyPatch) -> None:
    rotations = [object()]
    monkeypatch.setattr(providers, "get_rotations", lambda: rotations)

    service = providers.get_user_rotations_service()

    assert service._rotations == rotations


def test_get_user_rotations_service_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers, "get_rotations", lambda: [])

    assert providers.get_user_rotations_service() is providers.get_user_rotations_service()
