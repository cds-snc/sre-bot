"""Unit tests for idempotency cache abstract base class."""

import pytest
from abc import ABC

from infrastructure.idempotency.cache import IdempotencyCache

pytestmark = pytest.mark.unit


class TestIdempotencyCacheInterface:
    """Tests for IdempotencyCache abstract base class."""

    def test_cache_is_abstract_base_class(self):
        """IdempotencyCache is an abstract base class."""
        assert issubclass(IdempotencyCache, ABC)

    def test_cache_cannot_be_instantiated_directly(self):
        """IdempotencyCache cannot be instantiated directly (is abstract)."""
        with pytest.raises(TypeError):
            IdempotencyCache()

    def test_cache_defines_get_method(self):
        """IdempotencyCache defines required get method."""
        assert hasattr(IdempotencyCache, "get")
        assert callable(getattr(IdempotencyCache, "get"))

    def test_cache_defines_set_method(self):
        """IdempotencyCache defines required set method."""
        assert hasattr(IdempotencyCache, "set")
        assert callable(getattr(IdempotencyCache, "set"))

    def test_cache_defines_clear_method(self):
        """IdempotencyCache defines required clear method."""
        assert hasattr(IdempotencyCache, "clear")
        assert callable(getattr(IdempotencyCache, "clear"))

    def test_cache_defines_get_stats_method(self):
        """IdempotencyCache defines required get_stats method."""
        assert hasattr(IdempotencyCache, "get_stats")
        assert callable(getattr(IdempotencyCache, "get_stats"))
