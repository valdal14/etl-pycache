from abc import ABC, abstractmethod


class BaseCache(ABC):
    @abstractmethod
    def set(self, key: str, payload: str) -> None:
        """
        Saves the string payload to the cache.

        Args:
            key (str): The string used to set the cache
        """
        pass

    @abstractmethod
    def get(self, key: str) -> str | None:
        """
        Retrieves the string payload from the cache.

        Args:
            key (str): The string used to get the cache
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Removes the payload from the cache.

        Args:
            key (str): The string used to delete the cache
        """
        pass
