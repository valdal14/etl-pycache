import time

from etl_pycache.local_cache import LocalDiskCache


def test_capacity_eviction_protects_disk(tmp_path):
    """
    Verifies that when max_entries is set, the cache automatically deletes
    the oldest files to stay under the capacity limit.
    """
    # Initialize with a strict limit of 3 files
    cache = LocalDiskCache(cache_dir=str(tmp_path), max_entries=3)

    # Write 5 files sequentially
    for i in range(1, 6):
        cache.set(f"key_{i}", f"payload_{i}")
        # Sleep for a tiny fraction of a second to ensure the OS gives
        # each file a distinct, sequential modification timestamp.
        time.sleep(0.05)

    # Verify the total file count in the directory
    cache_files = list(tmp_path.glob("*.cache"))
    assert len(cache_files) == 3, f"Expected 3 files, but found {len(cache_files)}!"

    # 4. Verify exactly WHICH files survived (The Oldest-First rule)
    # The first two should be physically gone
    assert cache.get("key_1") is None, "key_1 should have been evicted!"
    assert cache.get("key_2") is None, "key_2 should have been evicted!"

    # The last three should still be perfectly intact
    assert cache.get("key_3") == "payload_3"
    assert cache.get("key_4") == "payload_4"
    assert cache.get("key_5") == "payload_5"
