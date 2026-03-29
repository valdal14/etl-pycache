# etl-pycache

A robust, persistent, disk-backed and S3-enabled LRU cache designed specifically for Data Engineering (ETL) pipelines. 

## ⚠️ The Problem
Data pipelines frequently make expensive API calls, run heavy transformations, and handle large payloads (like heavy Strings containing XML). If the final `load` step to a destination warehouse fails due to a network timeout or credential issue, pipelines typically have to start from scratch. This wastes compute resources, consumes API quotas, and drastically slows down developer velocity during debugging.

## ✅ The Solution
`etl-pycache` introduces a lightweight, persistent caching layer. It saves the state of your transformed data. If a pipeline fails downstream, it can read the fully transformed state directly from the cache on the next run, completely bypassing the extraction and transformation phases.

**Core Benefits:**
* **Idempotency:** Guarantees that rerunning a failed pipeline won't duplicate extraction tasks.
* **Cost Efficiency:** Prevents paying for the exact same compute or API queries twice during a retry.
* **Developer Velocity:** Rapidly debug downstream load operations without waiting for upstream transformations to finish.
* **Polymorphic By Design:** Natively supports strings, bytes, dictionaries, lists, and byte streams without requiring manual serialization.

---

## 👨🏼‍💻 Core Interface
The library enforces a strict contract for all cache implementations to ensure predictability across different environments:

```python
from etl_pycache.interfaces import BaseCache

# The contract guarantees these methods are available
cache.set(key="payload_123", payload="<dataset>...</dataset>")
data = cache.get(key="payload_123")
cache.delete(key="payload_123")
```

---

## 🚀 Quick Start: The Developer Cheat Sheet

`etl-pycache` provides a completely unified developer experience. Whether you are caching to a local hard drive for an Airflow worker, or streaming compressed data to AWS S3, the method signatures remain exactly the same.

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

## 🤝 Contributing
We welcome contributions! To maintain enterprise-grade code quality, this project uses strict formatting, linting, and testing pipelines.

1. Clone the repository and install all dependencies: `poetry install`
2. Run the formatter: `poetry run python3 -m ruff format .`
3. Run the linter: `poetry run python3 -m ruff check --fix .`
4. Run the tests: `poetry run python3 -m pytest`