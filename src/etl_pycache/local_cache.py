import json
import time
from collections.abc import Iterator as ABCIterator
from hashlib import sha256
from pathlib import Path

from .interfaces import BaseCache, PayloadType


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
                files will be stored. Defaults to ".cache", which creates a hidden
                folder in the current working directory. For ephemeral environments
                (like Docker containers), this should be set to an absolute path
                pointing to a persistent mounted volume (e.g., "/mnt/shared_cache")
                to prevent data loss upon container restart.
        """
        self.cache_dir = Path(cache_dir)
        self._make_path(self.cache_dir)

    def set(self, key: str, payload: PayloadType, ttl_seconds: int | None = None) -> None:
        """
        Serializes the polymorphic payload and writes it to a securely hashed file.

        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The data to serialize and save to disk.
            ttl_seconds (int | None, optional): The Time-To-Live in seconds.
                If provided, the cache entry will expire and be deleted after this time.
        """
        path = self._get_file_path(key)
        self._save_payload(path, payload)
        self._save_meta_file(path, ttl_seconds)

    def get(self, key: str) -> PayloadType | None:
        """
        Reads the cached file from the local disk and returns the deserialized payload.

        Args:
            key (str): The unique identifier for the cache entry.

        Returns:
            PayloadType | None: The cached data, or None if the file does not exist.
        """
        path = self._get_file_path(key)

        # check if the cache exists
        if not path.exists():
            return None

        # check if the meta file exists
        if self._is_expired(path):
            self.delete(key)
            return None

        raw_data = path.read_bytes()

        try:
            # Attempt to decode as standard text
            text_data = raw_data.decode("utf-8")
            try:
                # Attempt to parse as a JSON collection
                parsed_json = json.loads(text_data)

                if isinstance(parsed_json, (dict, list)):
                    return parsed_json

                # If it parsed a primitive, fall back to the string
                return text_data

            except json.JSONDecodeError:
                # return a string
                return text_data
        except UnicodeDecodeError:
            # returns raw binary data that cannot be read as text
            return raw_data

    def get_stream(self, key: str, chunk_size: int = 65536) -> ABCIterator | None:
        """
        Retrieves a cached file as a memory-efficient byte stream.

        Bypasses the heuristic deserialization engine to safely read massive
        files (e.g., 10GB+) without causing Out-Of-Memory (OOM) crashes.

        Args:
            key (str): The unique identifier for the cache entry.
            chunk_size (int, optional): The number of bytes to read per yield.
                Defaults to 65536 (64KB).

        Returns:
            ABCIterator | None: A generator yielding raw bytes, or None if missing.
        """
        path = self._get_file_path(key)

        # check if the cache exists
        if not path.exists():
            return None

        # check if the meta file exists
        if self._is_expired(path):
            self.delete(key)
            return None

        def _stream_generator() -> ABCIterator:
            with path.open(mode="rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        return _stream_generator()

    def delete(self, key: str) -> None:
        """
        Physically removes the specific cache file and its TTL sidecar from the hard drive.

        Args:
            key (str): The unique identifier for the cache entry to delete.
        """
        path = self._get_file_path(key)
        meta_path = path.with_suffix(".meta")

        if path.exists():
            path.unlink()

        if meta_path.exists():
            meta_path.unlink()

    def get_local_cache_name(self) -> str:
        """
        Retrieves the absolute or relative path string of the current cache directory.

        Returns:
            str: The string representation of the cache directory path.
        """
        return str(self.cache_dir)

    def _make_path(self, path: Path) -> None:
        """
        Safely creates the directory structure on the OS.

        Args:
            path (Path): The pathlib.Path object representing the directory to create.
                Ignores the command if the directory already exists.
        """
        path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """
        Secures the cache key by hashing it into a valid, safe OS filename.

        Args:
            key (str): The raw string key provided by the user.

        Returns:
            Path: The full absolute or relative path to the specific .cache file.
        """
        hashed_key = sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{hashed_key}.cache"

    # NOTE: - Internal Helper Methods #################################################################

    def _save_payload(self, path: Path, payload: PayloadType) -> None:
        """
        Routes the payload to the appropriate serialization and I/O method based on its type.

        Args:
            path (Path): The hashed file path where the data should be saved.
            payload (PayloadType): The data to inspect and route.

        Raises:
            NotImplementedError: If the payload is an unsupported type or an Iterator.
        """
        if isinstance(payload, str):
            self._save_str_payload(path, payload)
        elif isinstance(payload, bytes):
            self._save_bytes_payload(path, payload)
        elif isinstance(payload, (list, dict)):
            self._save_collection_payload(path, payload)
        elif isinstance(payload, ABCIterator):
            self._save_stream_payload(path, payload)
        else:
            raise NotImplementedError(
                "This payload type or streaming Iterator is not yet supported."
            )

    def _save_str_payload(self, path: Path, payload: PayloadType) -> None:
        """
        Writes a standard Python string to disk using UTF-8 encoding.

        Args:
            path (Path): The target file path.
            payload (str): The string data to write.
        """
        path.write_text(payload, encoding="utf-8")

    def _save_bytes_payload(self, path: Path, payload: PayloadType) -> None:
        """
        Writes raw binary data directly to disk.

        Args:
            path (Path): The target file path.
            payload (bytes): The binary data to write.
        """
        path.write_bytes(payload)

    def _save_collection_payload(self, path: Path, payload: PayloadType) -> None:
        """
        Serializes a Python list or dictionary into a JSON string, then saves it.

        Args:
            path (Path): The target file path.
            payload (list | dict): The collection to serialize.
        """
        str_collection = json.dumps(payload)
        self._save_str_payload(path, str_collection)

    def _save_stream_payload(self, path: Path, payload: PayloadType) -> None:
        """
        Streams an iterator of bytes directly to the disk in chunks.

        This method uses unbuffered binary writing to prevent Out-Of-Memory (OOM)
        errors when caching massive datasets (e.g., 10GB+ files).

        Args:
            path (Path): The hashed target file path where the stream will be written.
            payload (PayloadType): A generator or iterator yielding raw bytes.
        """
        with path.open(mode="wb") as f:
            for chunk in payload:
                f.write(chunk)

    def _save_meta_file(self, path: Path, ttl_seconds: int | None) -> None:
        """
        Manages the TTL sidecar file for a given cache entry.

        If a TTL is provided, it calculates the expiration and saves a .meta JSON file.
        If no TTL is provided, it ensures any pre-existing .meta file is deleted so
        the new cache entry doesn't accidentally inherit an old expiration.

        Args:
            path (Path): The physical Path object of the base .cache file.
            ttl_seconds (int | None): The time-to-live in seconds, or None for infinite.
        """
        meta_path = path.with_suffix(".meta")

        if ttl_seconds is not None:
            expiration_timestamp = time.time() + ttl_seconds
            meta_data = self._gen_meta_object(expiration_timestamp, ttl_seconds)
            meta_path.write_text(json.dumps(meta_data), encoding="utf-8")
        else:
            # Edge Case: Clean up the old sidecar if the new payload has no TTL
            if meta_path.exists():
                meta_path.unlink()

    def _gen_meta_object(self, expiration_timestamp: float, ttl_seconds: int) -> dict:
        """
        Constructs the dictionary payload for the TTL sidecar file.

        Args:
            expiration_timestamp (float): The exact Unix timestamp when the file expires.
            ttl_seconds (int): The original TTL duration provided by the user.

        Returns:
            dict: The standardized schema for the .meta JSON file.
        """
        return {"expires_at": expiration_timestamp, "ttl_seconds": ttl_seconds}

    def _is_expired(self, path: Path) -> bool:
        """
        Reads the .meta sidecar file to determine if the cache entry has expired.

        Args:
            path (Path): The physical Path object of the base .cache file.

        Returns:
            bool: True if the file has expired, False if it is still valid or has no TTL.
        """
        meta_path = path.with_suffix(".meta")

        if not meta_path.exists():
            # If there is no sidecar file, it means this entry has no TTL and lives forever.
            return False

        # Read the sidecar file and compare the timestamp to the current clock
        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))

        return time.time() >= meta_data["expires_at"]
