import json
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

    def set(self, key: str, payload: PayloadType) -> None:
        """
        Serializes the polymorphic payload and writes it to a securely hashed file.

        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The data to serialize and save to disk.
        """
        path = self._get_file_path(key)
        self._save_payload(path, payload)

    def get(self, key: str) -> PayloadType | None:
        """
        Reads the cached file from the local disk and returns the deserialized payload.

        Args:
            key (str): The unique identifier for the cache entry.

        Returns:
            PayloadType | None: The cached data, or None if the file does not exist.
        """
        path = self._get_file_path(key)

        if not path.exists():
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

    def delete(self, key: str) -> None:
        """
        Physically removes the specific cache file from the hard drive if it exists.

        Args:
            key (str): The unique identifier for the cache entry to delete.
        """
        path = self._get_file_path(key)
        if path.exists():
            path.unlink()

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
        with path.open(mode="wb") as f:
            for chunk in payload:
                f.write(chunk)
