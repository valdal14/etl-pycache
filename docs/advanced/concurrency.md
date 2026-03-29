# Enterprise Concurrency (File Locking)

`etl-pycache` is built for distributed data pipelines. The `LocalDiskCache` engine features a custom, zero-dependency, OS-native file locking mechanism. 

Whether you are running 50 parallel Airflow workers on Linux or local threads on Windows, the cache automatically coordinates Read/Write access using `fcntl` (POSIX) or `msvcrt` (Windows). 

**Zero configuration is required.** The locking is completely transparent to the developer. If multiple workers target the exact same cache key simultaneously, the engine automatically queues them to prevent file corruption and deadlocks, raising a timeout only if a worker holds a lock for an abnormal duration.