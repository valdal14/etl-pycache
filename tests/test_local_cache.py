import pytest
import tempfile
from pathlib import Path
from etl_pycache.local_cache import LocalDiskCache

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
    base_cache = LocalDiskCache(cache_dir=setup_local_cache)
    
    assert isinstance(base_cache, LocalDiskCache)
    # The temporary directory path is now safely injected
    assert setup_local_cache in base_cache.get_local_cache_name()

def test_local_cache_instance_make_path_success(setup_local_cache):
    base_cache = LocalDiskCache(cache_dir=setup_local_cache)
    path_str = base_cache.get_local_cache_name()
    
    path = Path(path_str)
    assert path.is_dir()