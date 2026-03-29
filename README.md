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

## 🚦 Roadmap (Towards V1.0.0)

- [x] Define abstract base interface and project scaffolding.
- [x] Implement local disk caching logic with polymorphic serialization and memory-safe streaming.
- [x] Implement TTL (Time-To-Live) expiration policies.
- [x] Implement AWS S3 cloud cache backend.
- [x] Add concurrency control (file locking) for parallel workers.
- [x] Implement compression for large text/XML payloads.
- [ ] Implement LRU (Least Recently Used) capacity eviction (*LocalDiskCache).
- [ ] Build official documentation site using MkDocs.

---

### 🔒 Enterprise Concurrency (File Locking)

`etl-pycache` is built for distributed data pipelines. The `LocalDiskCache` engine features a custom, zero-dependency, OS-native file locking mechanism. 

Whether you are running 50 parallel Airflow workers on Linux or local threads on Windows, the cache automatically coordinates Read/Write access using `fcntl` (POSIX) or `msvcrt` (Windows). 

**Zero configuration is required.** The locking is completely transparent to the developer. If multiple workers target the exact same cache key simultaneously, the engine automatically queues them to prevent file corruption and deadlocks, raising a timeout only if a worker holds a lock for an abnormal duration.

---

### 🗜️ Native Payload Compression

XML and JSON payloads are notoriously verbose. `etl-pycache` includes a native, zero-dependency compression engine using Python's built-in `gzip` library. 

By simply passing `compress=True` to the `set` method, the engine will aggressively compress your data *before* writing it to the local disk or streaming it over the network to AWS S3. 

```python
# A 100MB XML string will be shrunk down to ~12MB on your hard drive or S3 bucket
cache.set("massive_xml_payload", my_xml_string, compress=True)

# The get() method automatically detects the compression flag and decompresses on the fly
data = cache.get("massive_xml_payload")
```

Note: To ensure memory safety and prevent Out-Of-Memory crashes, stream payloads (ABCIterator) deliberately bypass compression.

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

## 💾 Usage: S3Cache (AWS S3 Cloud Backend)

The `S3Cache` engine implements the exact same `BaseCache` interface but securely streams your data directly into an AWS S3 bucket. 

**Installation:**
To keep the core library lightweight, the AWS SDK (`boto3`) is an optional dependency. You must install the package with the `s3` extra to use this backend:

```bash
# Using pip
pip install "etl-pycache[s3]"

# Using poetry
poetry add etl-pycache --extras s3
```

You can let `boto3` automatically discover your AWS environment variables, or explicitly inject your own authenticated client. The engine natively supports memory-safe streaming (`upload_fileobj`) and TTL expiration via S3 Object Metadata, meaning no cleanup scripts or sidecar files are required.

```python
import boto3
from etl_pycache.s3_cache import S3Cache

# 1. Initialize with an explicitly authenticated client
s3_client = boto3.client(
    "s3", 
    aws_access_key_id="YOUR_ACCESS_KEY",
    aws_secret_access_key="YOUR_SECRET_KEY",
    region_name="eu-west-1"
)
cache = S3Cache(bucket_name="my-production-bucket", client=s3_client)

# 2. Stream a massive payload to S3 with a 1-hour TTL
# The engine pipes the generator directly to the cloud without bloating your RAM
cache.set("my_folder/financial_data", my_byte_generator, ttl_seconds=3600)

# 3. Retrieve the stream directly from the cloud
# Returns a boto3 StreamingBody that flawlessly implements the Python Iterator protocol
stream = cache.get_stream("my_folder/financial_data")
```

---

## 🚀 Quick Start: The Developer Cheat Sheet

`etl-pycache` provides a completely unified developer experience. Whether you are caching to a local hard drive for an Airflow worker, or streaming compressed data to AWS S3, the method signatures remain exactly the same.

Here is a complete, real-world example of caching a massive payload with both TTL expiration and native compression:

```python
import boto3
from etl_pycache.local_cache import LocalDiskCache
from etl_pycache.s3_cache import S3Cache

# ==========================================
# 1. INITIALIZATION
# ==========================================

# Local Disk (Perfect for local workers or Celery)
local_cache = LocalDiskCache(cache_dir="/tmp/my_etl_cache")

# AWS S3 (Perfect for distributed cloud sharing)
s3_client = boto3.client("s3", region_name="eu-west-1")
cloud_cache = S3Cache(bucket_name="canda-anaplan-demo", client=s3_client)

# ==========================================
# 2. WRITING DATA (TTL + Compression)
# ==========================================
my_massive_xml_payload = "<dataset>... 500MB of data ...</dataset>"

# Save locally: Expires in 1 hour, shrunk by ~80% on disk, locked for OS concurrency
local_cache.set("financial_run_001", my_massive_xml_payload, ttl_seconds=3600, compress=True)

# Save to Cloud: Expires in 1 hour, shrunk by ~80% before upload to save AWS costs
cloud_cache.set("deve/financial_run_001", my_massive_xml_payload, ttl_seconds=3600, compress=True)

# ==========================================
# 3. READING DATA
# ==========================================

# You do NOT need to check if the file is expired or compressed!
# The engine automatically validates the TTL, deletes it if expired, 
# and decompresses the bytes on the fly before returning your data.

local_data = local_cache.get("financial_run_001")
if local_data:
    print("Successfully read and decompressed from local disk!")

cloud_data = cloud_cache.get("deve/financial_run_001")
if cloud_data:
    print("Successfully read and decompressed from AWS S3!")
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