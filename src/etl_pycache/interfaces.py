from abc import ABC, abstractmethod
from typing import Iterator

# Defines the supported data types for the cache payload
PayloadType = str | bytes | dict | list | Iterator[bytes]


class BaseCache(ABC):
    @abstractmethod
    def set(self, key: str, payload: PayloadType) -> None:
        """
        Saves the payload to the cache.

        Args:
            key (str): The unique identifier for the cache entry.
            payload (PayloadType): The data to cache. Must be a string,
                bytes, dict, list, or a byte stream.
        """
        pass

    @abstractmethod
    def get(self, key: str) -> PayloadType | None:
        """
        Retrieves the payload from the cache.

        Args:
            key (str): The unique identifier for the cache entry.

        Returns:
            PayloadType | None: The cached data, or None if the key does not exist.
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Removes the payload from the cache.

        Args:
            key (str): The unique identifier for the cache entry.
        """
        pass
