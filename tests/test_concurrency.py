import concurrent.futures

from etl_pycache.local_cache import LocalDiskCache


def test_concurrent_writes_do_not_corrupt_file(tmp_path):
    """
    Simulates 20 parallel Airflow workers attempting to write and read
    to the exact same cache file simultaneously.
    """
    cache = LocalDiskCache(cache_dir=str(tmp_path))
    key = "concurrent_chaos_test"

    def worker(worker_id: int):
        # Create a sufficiently large payload to ensure it takes a few milliseconds to write
        payload = {"worker_id": worker_id, "data": "X" * 50000}

        # Write to disk
        cache.set(key, payload)

        # Immediately read from disk
        result = cache.get(key)

        # If the file was corrupted by another thread, result will be None or crash
        assert result is not None
        assert "worker_id" in result

    # Spin up 20 parallel threads and unleash them on the cache
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker, i) for i in range(20)]

        for future in concurrent.futures.as_completed(futures):
            # If any thread crashed (e.g., JSONDecodeError), this will raise the exception
            future.result()

    # Verify the file survived and the final state is perfectly valid JSON
    final_data = cache.get(key)
    assert final_data is not None
