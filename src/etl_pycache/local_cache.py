import gzip
import json
import time
from collections.abc import Iterator as ABCIterator
from hashlib import sha256
from pathlib import Path

from .interfaces import BaseCache, PayloadType
from .lock_manager import CacheLock


class LocalDiskCache(BaseCache):
    """
    A persistent, disk-backed implementation of the BaseCache.

    This cache securely stores polymorphic data types to the local filesystem.
    It uses SHA-256 hashing on all keys to prevent directory traversal attacks
    and ensure cross-platform filename compatibility.
    """

    def __init__(self, cache_dir: str = ".cache"):
        """
        Initializes the cache and ensures the storage directory exists.

        Args:
            cache_dir (str, optional): The directory path where the physical cache
                files will be stored. Defaults to ".cache".
        """
        self.cache_dir = Path(cache_dir)
        self._make_path(self.cache_dir)

    def set(
        self, key: str, payload: PayloadType, ttl_seconds: int | None = None, compress: bool = False
    ) -> None:
        """
        Serializes the polymorphic payload and writes it to a securely hashed file.

        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The data to serialize and save to disk.
            ttl_seconds (int | None, optional): The Time-To-Live in seconds.
            compress (bool, optional): If True, aggressively compresses strings, dicts,
                lists, and bytes using gzip to save disk space. Defaults to False.
        """
        path = self._get_file_path(key)
        lock_path = str(path.with_suffix(".lock"))

        # Lock the entire transaction (Payload + Meta file)
        with CacheLock(lock_path):
            self._save_payload(path, payload, compress)
            self._save_meta_file(path, ttl_seconds, compress)

    def get(self, key: str) -> PayloadType | None:
        """
        Reads the cached file from the local disk, handling decompression and deserialization.

        Args:
            key (str): The unique identifier for the cache entry.

        Returns:
            PayloadType | None: The cached data, or None if the file does not exist.
        """
        path = self._get_file_path(key)
        lock_path = str(path.with_suffix(".lock"))

        with CacheLock(lock_path):
            if not path.exists():
                return None

            if self._is_expired(path):
                self._delete_files(path)
                return None

            raw_data = path.read_bytes()

            # Check the .meta file for the compression flag
            is_compressed = False
            meta_path = path.with_suffix(".meta")
            if meta_path.exists():
                meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                is_compressed = meta_data.get("compressed", False)

        # Decompression and Deserialization happen OUTSIDE the lock to free up the file
        if is_compressed:
            raw_data = gzip.decompress(raw_data)

        try:
            text_data = raw_data.decode("utf-8")
            try:
                parsed_json = json.loads(text_data)
                if isinstance(parsed_json, (dict, list)):
                    return parsed_json
                return text_data
            except json.JSONDecodeError:
                return text_data
        except UnicodeDecodeError:
            return raw_data

    def get_stream(self, key: str, chunk_size: int = 65536) -> ABCIterator | None:
        """
        Retrieves a cached file as a memory-efficient byte stream.
        Note: Compressed files are returned as compressed byte chunks.
        """
        path = self._get_file_path(key)
        lock_path = str(path.with_suffix(".lock"))

        with CacheLock(lock_path):
            if not path.exists():
                return None

            if self._is_expired(path):
                self._delete_files(path)
                return None

        def _stream_generator() -> ABCIterator:
            with CacheLock(lock_path):
                with path.open(mode="rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk

        return _stream_generator()

    def delete(self, key: str) -> None:
        """Physically removes the specific cache file and its TTL sidecar."""
        path = self._get_file_path(key)
        lock_path = str(path.with_suffix(".lock"))

        with CacheLock(lock_path):
            self._delete_files(path)

    def get_local_cache_name(self) -> str:
        """Retrieves the absolute or relative path string of the current cache directory."""
        return str(self.cache_dir)

    def _make_path(self, path: Path) -> None:
        """Safely creates the directory structure on the OS."""
        path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Secures the cache key by hashing it into a valid, safe OS filename."""
        hashed_key = sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{hashed_key}.cache"

    # NOTE: - Internal Helper Methods #################################################################

    def _save_payload(self, path: Path, payload: PayloadType, compress: bool) -> None:
        """
        Routes the payload to the appropriate serialization and I/O method based on its type.
        """
        if isinstance(payload, str):
            self._save_str_payload(path, payload, compress)
        elif isinstance(payload, bytes):
            self._save_bytes_payload(path, payload, compress)
        elif isinstance(payload, (list, dict)):
            self._save_collection_payload(path, payload, compress)
        elif isinstance(payload, ABCIterator):
            self._save_stream_payload(path, payload)
        else:
            raise NotImplementedError(
                "This payload type or streaming Iterator is not yet supported."
            )

    def _save_str_payload(self, path: Path, payload: str, compress: bool) -> None:
        """
        Writes a standard Python string to disk, natively compressing it if requested.
        """
        if compress:
            compressed_bytes = gzip.compress(payload.encode("utf-8"))
            path.write_bytes(compressed_bytes)
        else:
            path.write_text(payload, encoding="utf-8")

    def _save_bytes_payload(self, path: Path, payload: bytes, compress: bool) -> None:
        """
        Writes raw binary data directly to disk, compressing if requested.
        """
        if compress:
            path.write_bytes(gzip.compress(payload))
        else:
            path.write_bytes(payload)

    def _save_collection_payload(self, path: Path, payload: list | dict, compress: bool) -> None:
        """
        Serializes a Python collection into JSON, then delegates to string saving (inheriting compression).
        """
        str_collection = json.dumps(payload)
        self._save_str_payload(path, str_collection, compress)

    def _save_stream_payload(self, path: Path, payload: ABCIterator) -> None:
        """
        Streams raw bytes to disk. Bypasses compression to maintain memory safety.
        """
        with path.open(mode="wb") as f:
            for chunk in payload:
                f.write(chunk)

    def _save_meta_file(self, path: Path, ttl_seconds: int | None, compress: bool) -> None:
        """
        Manages the TTL and compression sidecar file.
        Forces creation if compression is enabled to ensure safe reads.
        """
        meta_path = path.with_suffix(".meta")

        if ttl_seconds is not None or compress:
            expiration_timestamp = (time.time() + ttl_seconds) if ttl_seconds else 0
            ttl_val = ttl_seconds if ttl_seconds else 0

            meta_data = self._gen_meta_object(expiration_timestamp, ttl_val, compress)
            meta_path.write_text(json.dumps(meta_data), encoding="utf-8")
        else:
            if meta_path.exists():
                meta_path.unlink()

    def _gen_meta_object(
        self, expiration_timestamp: float, ttl_seconds: int, compress: bool
    ) -> dict:
        """Constructs the dictionary payload for the TTL and compression sidecar file."""
        return {
            "expires_at": expiration_timestamp,
            "ttl_seconds": ttl_seconds,
            "compressed": compress,
        }

    def _is_expired(self, path: Path) -> bool:
        """
        Reads the .meta sidecar file to determine if the cache entry has expired.
        Safely ignores files mapped with a 0 expiration timestamp (infinite TTL).
        """
        meta_path = path.with_suffix(".meta")

        if not meta_path.exists():
            return False

        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
        expires_at = meta_data.get("expires_at", 0)

        # 0 means no TTL was provided (it only has a .meta file for compression)
        if expires_at == 0:
            return False

        return time.time() >= expires_at

    def _delete_files(self, path: Path) -> None:
        """Internal helper to safely unlink the cache and meta files."""
        meta_path = path.with_suffix(".meta")
        lock_path = path.with_suffix(".lock")

        if path.exists():
            path.unlink()

        if meta_path.exists():
            meta_path.unlink()

        if lock_path.exists():
            try:
                lock_path.unlink()
            except OSError:
                pass
