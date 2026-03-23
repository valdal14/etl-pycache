import pytest

from etl_pycache.interfaces import BaseCache


def test_base_cache_cannot_be_instantiated():
    """Asserts that the interface itself cannot be used directly."""
    with pytest.raises(TypeError):
        # This should fail because it has abstract methods
        _ = BaseCache()


def test_dummy_cache_missing_methods_raises_error():
    """Asserts that a child class must implement all abstract methods."""

    class IncompleteCache(BaseCache):
        # We only implement 'get', forgetting 'set' and 'delete'
        def get(self, key: str) -> str | None:
            return None

    with pytest.raises(TypeError):
        # This will fail because 'set' and 'delete' are missing
        _ = IncompleteCache()
