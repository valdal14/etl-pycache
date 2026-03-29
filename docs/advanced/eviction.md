# Capacity Protection (LRU Eviction)

Time-To-Live (TTL) manages *time*, but it doesn't manage *space*. If your pipeline experiences a massive volume spike or a historical backfill, caching thousands of large files could fill your worker's hard drive and crash the host server before the TTL expires.

`LocalDiskCache` includes a Least Recently Used (LRU) capacity ceiling to act as a hard safety valve. By setting `max_entries`, the engine will constantly monitor your disk footprint. If the limit is breached, it automatically identifies and destroys the oldest cache files to make room for new data.

```python
from etl_pycache.local_cache import LocalDiskCache

# Initialize a cache that will never exceed 1,000 files
cache = LocalDiskCache(cache_dir="/tmp/safe_cache", max_entries=1000)

# If this is the 1001st item, the engine automatically deletes the oldest
# file on the hard drive before saving this one.
cache.set("new_financial_run", massive_payload)
```

*(Note: Capacity eviction is only required for the local disk. `S3Cache` relies on native AWS S3 Lifecycle Policies to manage cloud storage limits).*