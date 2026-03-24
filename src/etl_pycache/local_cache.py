from .interfaces import BaseCache, PayloadType
from hashlib import sha256
from pathlib import Path, PurePath

class LocalDiskCache(BaseCache):

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self._make_path(self.cache_dir)
        

    def set(self, key: str, payload: PayloadType) -> None:
        pass

    def get(self, key: str) -> PayloadType | None:
        pass

    def delete(self, key: str) -> None:
        pass

    def get_local_cache_name(self) -> str:
        """ 
        Retrieve the chosen cache name

        Returns:
            str: The current cache name
        """
        return str(self.cache_dir)
    
    def _make_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
    

#self.cache_dir = sha256(cache_dir.encode("utf-8"))
#return sha256(self.cache_dir.digest().decode("utf-8"))