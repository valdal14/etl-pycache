import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from etl_pycache.local_cache import LocalDiskCache, PayloadType


@pytest.fixture
def setup_local_cache():
    """
    Creates a temporary directory for the cache.
    Using 'yield' inside a context manager ensures the directory
    is safely deleted from the OS after the test completes.
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


def test_local_cache_instance_custom_cache_name(setup_local_cache):
    sut = make_sut(setup_local_cache)

    assert isinstance(sut.cache, LocalDiskCache)
    # The temporary directory path is now safely injected
    assert setup_local_cache in sut.cache.get_local_cache_name()


def test_local_cache_instance_make_path_success(setup_local_cache):
    sut = make_sut(setup_local_cache)
    dir_path = sut.cache.get_local_cache_name()

    path = Path(dir_path)
    assert path.is_dir()


def test_get_file_path_secures_malicious_key(setup_local_cache):
    malicious_key = "../../../etc/passwd"
    sut = make_sut(setup_local_cache, malicious_key)
    path = sut.cache._get_file_path(sut.key)
    assert "../" not in path.name
    assert path.parent == Path(setup_local_cache)


def test_local_cache_instance_produces_different_files_for_each_given_key(setup_local_cache):
    sut = make_sut(setup_local_cache)
    path_one = sut.cache._get_file_path("pipeline_a_data")
    path_two = sut.cache._get_file_path("pipeline_b_data")
    assert path_one != path_two


# NOTE: - Test's Helpers ##########################################################################
@dataclass
class MockedCache:
    cache: LocalDiskCache
    key: str
    payload: PayloadType


def default_payload():
    return {
        "name": "Frieda",
        "isDog": True,
        "hobbies": ["eating", "sleeping", "barking"],
        "age": 8,
        "address": {"work": None, "home": ["Berlin", "Germany"]},
    }


def make_sut(
    fixture, key: str = "dict_key", payload: PayloadType = default_payload()
) -> MockedCache:
    return MockedCache(LocalDiskCache(cache_dir=fixture), key, payload)
