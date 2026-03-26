import pytest

from etl_pycache.interfaces import BaseCache, PayloadType


def test_base_cache_cannot_be_instantiated():
    """Asserts that the interface itself cannot be used directly."""
    with pytest.raises(TypeError):
        # This should fail because it has abstract methods
        _ = BaseCache()


def test_dummy_cache_missing_methods_raises_error():
    """Asserts that a child class must implement all abstract methods."""

    class IncompleteCache(BaseCache):
        # We only implement 'get', forgetting 'set' and 'delete'
        def get(self, key: str) -> PayloadType | None:
            return None

    with pytest.raises(TypeError):
        # This will fail because 'set' and 'delete' are missing
        _ = IncompleteCache()


def test_base_cache_enforces_get_stream_contract():
    # We build a dummy cache that "forgets" to implement get_stream
    class BadCache(BaseCache):
        def set(self, key, payload):
            pass

        def get(self, key):
            pass

        def delete(self, key):
            pass

        # Notice get_stream is missing!

    # Python should violently crash with a TypeError before it even instantiates
    with pytest.raises(TypeError) as exc_info:
        BadCache()

    # Assert the exact error message mentions the missing method
    error_msg = str(exc_info.value)
    assert "Can't instantiate abstract class" in error_msg
    assert "get_stream" in error_msg
