# etl-pycache

[![CI Pipeline](https://github.com/valdal14/etl-pycache/actions/workflows/ci.yml/badge.svg)](https://github.com/valdal14/etl-pycache/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

A robust, persistent, disk-backed LRU cache designed specifically for Data Engineering (ETL) pipelines. 

## ⚠️ The Problem
Data pipelines frequently make expensive API calls, run heavy transformations, and handle large payloads (like heavy Strings containing XML). If the final `load` step to a destination warehouse fails due to a network timeout or credential issue, pipelines typically have to start from scratch. This wastes compute resources, consumes API quotas, and drastically slows down developer velocity during debugging.

## ✅ The Solution
`etl-pycache` introduces a lightweight, persistent caching layer. It saves the state of your transformed data to disk. If a pipeline fails downstream, it can read the fully transformed state directly from the local disk cache on the next run, completely bypassing the extraction and transformation phases.

**Core Benefits:**
* **Idempotency:** Guarantees that rerunning a failed pipeline won't duplicate extraction tasks.
* **Cost Efficiency:** Prevents paying for the exact same compute or API queries twice during a retry.
* **Developer Velocity:** Rapidly debug downstream load operations without waiting for upstream transformations to finish.
* **Polymorphic By Design:** Natively supports strings, bytes, dictionaries, lists, and byte streams without requiring manual serialization before caching.

## 🚦 Roadmap

- [x] Define abstract base interface and project scaffolding.
- [x] Implement local disk caching logic with polymorphic serialization and memory-safe streaming.
- [x] Implement TTL (Time-To-Live) expiration policies.
- [ ] Implement LRU (Least Recently Used) capacity eviction.
- [ ] Add concurrency control (file locking) for parallel workers.
- [ ] Implement compression for large text/XML payloads.

---

## 👨🏼‍💻 Core Interface
The library enforces a strict contract for all cache implementations to ensure predictability across different environments:

```python
from etl_pycache.interface import BaseCache

# The contract guarantees these methods are available
cache.set(key="payload_123", payload="<xml>...</xml>")
data = cache.get(key="payload_123")
cache.delete(key="payload_123")
```

---

## 💾 Usage: LocalDiskCache

The `LocalDiskCache` is a secure, disk-backed implementation that automatically handles serialization for you. It uses SHA-256 hashing to prevent directory traversal attacks, meaning your cache keys are always safe to use as filenames.

### Polymorphic Type Support
You don't need to manually stringify your data. The cache automatically inspects and routes your payloads:
* **`str` & `bytes`**: Written directly to disk.
* **`dict` & `list`**: Automatically serialized to JSON on `set()`, and parsed back into Python collections on `get()`.

```python
from etl_pycache.local_cache import LocalDiskCache

# 1. Initialize the cache (Defaults to a hidden '.cache' folder in your project)
cache = LocalDiskCache(cache_dir=".cache")

# 2. Cache a dictionary directly! No json.dumps() needed.
pipeline_data = {"records_processed": 1042, "status": "success"}
cache.set("job_123_stats", pipeline_data)

# 3. Retrieve it later (It comes back as a dictionary!)
result = cache.get("job_123_stats")
print(type(result)) # <class 'dict'>

# 4. Clean up
cache.delete("job_123_stats")
```

### 🌊 Memory-Safe Streaming (10GB+ Datasets)
For massive datasets, `LocalDiskCache` supports chunked binary streaming to completely prevent Out-Of-Memory (OOM) crashes. Our `set` method natively accepts any Python `Iterator[bytes]`.

Here are the two most common ways to use it in production pipelines (like Airflow or Prefect):

#### Scenario A: Streaming from an API to the Cache
When downloading massive files from the web, do not load them into memory. Pass the HTTP library's built-in iterator directly to the cache.

```python
import requests
from etl_pycache.local_cache import LocalDiskCache

cache = LocalDiskCache()

# 1. Connect to the massive dataset and tell requests to stream it
response = requests.get("https://api.example.com/massive_dataset.csv", stream=True)

# 2. Hand the API's built-in iterator directly to your cache
cache.set("downloaded_dataset", response.iter_content(chunk_size=65536))
```

#### Scenario B: Streaming a Local File to the Cache
If you are moving or backing up massive local files (e.g., inside an Airflow DAG), use a simple Python generator to yield the file in chunks.

```python
from etl_pycache.local_cache import LocalDiskCache

cache = LocalDiskCache()

def read_in_chunks(file_path: str, chunk_size: int = 65536):
    """Safely yields a local file in memory-efficient chunks."""
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk

# Pass the generator execution directly into the cache
cache.set("local_backup", read_in_chunks("/path/to/massive_local_file.csv"))
```

#### Retrieving a Stream
When you need to read a massive file back out of the cache, explicitly use get_stream() to bypass standard memory loading:

```python
# Returns a memory-safe generator
stream = cache.get_stream("downloaded_dataset", chunk_size=65536)

for chunk in stream:
    # TODO: This is where your custom pipeline logic goes!
    # For example: parsing the bytes, writing to a database, etc.
    # Here is a simple example just printing the size of each chunk:
    print(f"Successfully processed a chunk of {len(chunk)} bytes")
```

---

### ⏳ Time-To-Live (TTL) Expiration
You can enforce automatic expiration on any cached payload by passing `ttl_seconds` to the `set` method. 

Under the hood, `etl-pycache` uses a **Sidecar Pattern**. When a TTL is provided, it safely writes a tiny `[key].meta` JSON file next to your `[key].cache` data file. When the data is requested, the engine checks the clock. If the TTL has passed, it automatically wipes both files from the OS and returns `None`.

```python
from etl_pycache.local_cache import LocalDiskCache

cache = LocalDiskCache()

# 1. Cache a payload for exactly 1 hour (3600 seconds)
cache.set("daily_report", {"status": "success"}, ttl_seconds=3600)

# 2. Retrieve the payload (Returns the dictionary if within 1 hour)
result = cache.get("daily_report")

# 3. If accessed after 1 hour, it returns None and cleans up the hard drive
expired_result = cache.get("daily_report") 
# Returns: None
```

---

## 🤝 Contributing to etl-pycache

We welcome contributions! To maintain enterprise-grade code quality, this project uses strict formatting, linting, and testing pipelines.

### Prerequisites
* **Python 3.10+**
* **Poetry** (Dependency management)

### 1. Local Setup
Clone the repository and install all dependencies (including the `dev` group tools like Pytest and Ruff):

```bash
git clone git@github.com:valdal14/etl-pycache.git
cd etl-pycache
poetry install
```

### 2. Formatting & Linting (Ruff)
This project enforces strict PEP 8 compliance using **Ruff**. Before submitting any code, you must format and lint your changes. If you do not run these commands, the GitHub Actions CI pipeline will fail your Pull Request.

Run the formatter to automatically fix spacing, quotes, and line breaks:

```bash
poetry run python3 -m ruff format .
```

Run the linter to catch unused imports, bad variables, and logical style issues:

```bash
poetry run python3 -m ruff check --fix .
```

(Tip: I highly recommend installing the Ruff extension in your IDE and setting it to "Format on Save").

### 3. Running Tests (Pytest)

Every feature and bug fix must be covered by unit tests.

Run the entire test suite:

```bash
poetry run python3 -m pytest
```

### 4. The Pull Request Workflow

1. Create a feature branch (e.g., `feature/ETL-PYCACHE-123-redis-based-cache`).
2. Write your code and your tests.
3. Run Ruff (format and check) and Pytest.
4. Push your branch to GitHub and open a Pull Request against `main`.
5. Wait for the automated CI pipeline to verify your build before merging.