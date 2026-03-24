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
        pass

    def get(self, key: str) -> PayloadType | None:
        """
        Reads the cached file from the local disk and returns the deserialized payload.

        Args:
            key (str): The unique identifier for the cache entry.

        Returns:
            PayloadType | None: The cached data, or None if the file does not exist.
        """
        pass

    def delete(self, key: str) -> None:
        """
        Physically removes the specific cache file from the hard drive if it exists.

        Args:
            key (str): The unique identifier for the cache entry to delete.
        """
        pass

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
