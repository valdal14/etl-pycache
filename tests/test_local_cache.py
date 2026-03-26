import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from etl_pycache.local_cache import LocalDiskCache, PayloadType


# NOTE: - Instance and Directory creation Tests ###################################################
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


# NOTE: - Set method tests ########################################################################


def test_set_saves_string_payload(setup_local_cache):
    xml_string = """
        <note>
            <to>Grazia</to>
            <from>Val</from>
            <heading>Reminder</heading>
            <body>Don't forget to drink water!</body>
        </note>
    """
    sut = make_sut(setup_local_cache, "dad_key", xml_string)
    sut.cache.set(sut.key, xml_string)
    file_path = sut.cache._get_file_path("dad_key")
    assert file_path.is_file()


def test_set_saves_bytes_payload(setup_local_cache):
    str_bytes = "14".encode(encoding="utf-8")
    sut = make_sut(setup_local_cache, "dad_key", str_bytes)
    sut.cache.set(sut.key, str_bytes)
    file_path = sut.cache._get_file_path("dad_key")
    assert file_path.is_file()


def test_set_saves_list_payload(setup_local_cache):
    list_payload = [1, 2, 3, 4, 5]
    sut = make_sut(setup_local_cache, "dad_key", list_payload)
    sut.cache.set(sut.key, list_payload)
    file_path = sut.cache._get_file_path("dad_key")
    assert file_path.is_file()


def test_set_saves_dict_payload(setup_local_cache):
    sut = make_sut(setup_local_cache, "dad_key")
    sut.cache.set(sut.key, sut.payload)
    file_path = sut.cache._get_file_path("dad_key")
    assert file_path.is_file()


def test_set_throws_NotImplementedError(setup_local_cache):
    payload = 1
    sut = make_sut(setup_local_cache, "dad_key", payload)
    with pytest.raises(NotImplementedError):
        sut.cache.set(sut.key, payload)


# NOTE: - Get method tests ########################################################################


def test_get_returns_none(setup_local_cache):
    """Not setting the payload produces a None result"""
    sut = make_sut(setup_local_cache)
    res = sut.cache.get(sut.key)
    assert res is None


def test_get_returns_string(setup_local_cache):
    payload = "Hello World!"
    sut = make_sut(setup_local_cache, "str_key", payload)

    sut.cache.set(sut.key, payload)
    res = sut.cache.get("str_key")

    assert isinstance(res, str)
    assert res == payload


def test_get_returns_bytes(setup_local_cache):
    raw_bytes = b"\x80\x04\x95"
    sut = make_sut(setup_local_cache, "binary_key", raw_bytes)

    sut.cache.set(sut.key, raw_bytes)
    res = sut.cache.get("binary_key")

    # Prove it triggered the UnicodeDecodeError and fell back to bytes
    assert isinstance(res, bytes)
    # Prove the data wasn't corrupted
    assert res == raw_bytes


def test_get_returns_list(setup_local_cache):
    payload = ["Hello", "World", "!"]
    sut = make_sut(setup_local_cache, "list_key", payload)

    sut.cache.set(sut.key, payload)
    res = sut.cache.get("list_key")

    assert isinstance(res, list)
    assert res == payload


def test_get_returns_dic(setup_local_cache):
    sut = make_sut(setup_local_cache)

    sut.cache.set(sut.key, sut.payload)
    res = sut.cache.get(sut.key)

    assert isinstance(res, dict)
    assert res == sut.payload


# NOTE: - Delete method tests #####################################################################


def test_delete_returns_none(setup_local_cache):
    sut = make_sut(setup_local_cache)
    res = sut.cache.delete(sut.key)
    assert res is None


def test_delete_successfully_delete_cached_file(setup_local_cache):
    sut = make_sut(setup_local_cache)
    sut.cache.set(sut.key, sut.payload)

    # First assert it was created
    res = sut.cache.get(sut.key)
    assert isinstance(res, dict)
    assert res == sut.payload

    # Execute the deletion
    sut.cache.delete(sut.key)

    # Prove it is no longer available by trying to get it again
    deleted_res = sut.cache.get(sut.key)
    assert deleted_res is None


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
