"""Object storage abstraction with local filesystem implementation."""

import logging
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class ObjectStorage(Protocol):
    """Protocol for object storage backends.

    Key pattern: {collection_id}/{document_id}/{version_id}/{filename}
    """

    async def save(self, key: str, content: bytes) -> str:
        """Save content and return the storage URL/path."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve content by key."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete content. Return True if deleted, False if not found."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if content exists at the given key."""
        ...


class LocalStorage:
    """Local filesystem storage implementation.

    Files are stored at base_path / key where key follows the pattern
    {collection_id}/{document_id}/{version_id}/{filename}.
    """

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path.

        Raises ValueError if the key attempts path traversal (e.g. ../).
        """
        resolved = (self.base_path / key).resolve()
        if not str(resolved).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Path traversal detected in storage key: {key}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    async def save(self, key: str, content: bytes) -> str:
        """Save content to local filesystem and return the path."""
        path = self._resolve(key)
        path.write_bytes(content)
        logger.debug("storage_save key=%s size=%d", key, len(content))
        return str(path)

    async def get(self, key: str) -> bytes:
        """Read content from local filesystem."""
        path = self._resolve(key)
        return path.read_bytes()

    async def delete(self, key: str) -> bool:
        """Delete a file from local storage."""
        path = self._resolve(key)
        if path.exists():
            path.unlink()
            logger.debug("storage_delete key=%s", key)
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if a file exists in local storage."""
        return self._resolve(key).exists()


def get_storage(base_path: str) -> ObjectStorage:
    """Factory to create the configured storage backend."""
    return LocalStorage(base_path)