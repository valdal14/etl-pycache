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
- [ ] Implement local disk caching logic with string serialization.
- [ ] Implement LRU (Least Recently Used) eviction policies.
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