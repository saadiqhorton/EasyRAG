"""Unit tests for LocalStorage: save, get, delete, exists, path traversal protection."""

import pytest

from app.backend.services.storage import LocalStorage


class TestLocalStorageSave:
    """Tests for LocalStorage.save."""

    async def test_save_returns_path(self, tmp_path):
        """Arrange: create LocalStorage with a temp base path.
        Act: save content under a valid key.
        Assert: the returned path ends with the key and the file exists.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"
        content = b"hello world"

        result = await storage.save(key, content)

        assert result.endswith(key)
        assert (tmp_path / "store" / key).exists()

    async def test_save_creates_parent_directories(self, tmp_path):
        """Arrange: use a key with deep nested directories.
        Act: save content.
        Assert: all intermediate directories were created.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "a/b/c/d/deep.txt"

        await storage.save(key, b"deep")

        assert (tmp_path / "store" / "a" / "b" / "c" / "d" / "deep.txt").exists()

    async def test_save_overwrites_existing(self, tmp_path):
        """Arrange: save content, then save different content to the same key.
        Act: save twice with different content.
        Assert: the second content replaces the first.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"

        await storage.save(key, b"first")
        await storage.save(key, b"second")

        data = await storage.get(key)
        assert data == b"second"

    async def test_save_empty_content(self, tmp_path):
        """Arrange: use empty bytes as content.
        Act: save empty content.
        Assert: file exists and read returns empty bytes.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "empty/file.txt"

        await storage.save(key, b"")

        data = await storage.get(key)
        assert data == b""


class TestLocalStorageGet:
    """Tests for LocalStorage.get."""

    async def test_get_reads_saved_content(self, tmp_path):
        """Arrange: save known content.
        Act: get the content by key.
        Assert: returned bytes match what was saved.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"
        content = b"some content here"
        await storage.save(key, content)

        result = await storage.get(key)

        assert result == content

    async def test_get_nonexistent_raises(self, tmp_path):
        """Arrange: do not save anything.
        Act: try to get content from a nonexistent key.
        Assert: raises FileNotFoundError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(FileNotFoundError):
            await storage.get("no/such/key.txt")


class TestLocalStorageDelete:
    """Tests for LocalStorage.delete."""

    async def test_delete_existing_returns_true(self, tmp_path):
        """Arrange: save a file.
        Act: delete it.
        Assert: returns True and file is gone.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"
        await storage.save(key, b"data")

        result = await storage.delete(key)

        assert result is True
        assert not (tmp_path / "store" / key).exists()

    async def test_delete_nonexistent_returns_false(self, tmp_path):
        """Arrange: create storage but do not save any file.
        Act: delete a nonexistent key.
        Assert: returns False.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        result = await storage.delete("no/such/key.txt")

        assert result is False


class TestLocalStorageExists:
    """Tests for LocalStorage.exists."""

    async def test_exists_after_save(self, tmp_path):
        """Arrange: save content.
        Act: check if the key exists.
        Assert: returns True.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"
        await storage.save(key, b"data")

        result = await storage.exists(key)

        assert result is True

    async def test_exists_nonexistent(self, tmp_path):
        """Arrange: do not save anything.
        Act: check if a nonexistent key exists.
        Assert: returns False.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        result = await storage.exists("no/such/key.txt")

        assert result is False

    async def test_exists_after_delete(self, tmp_path):
        """Arrange: save then delete a file.
        Act: check if the key exists.
        Assert: returns False.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.txt"
        await storage.save(key, b"data")
        await storage.delete(key)

        result = await storage.exists(key)

        assert result is False


class TestLocalStoragePathTraversal:
    """Tests for path traversal protection in _resolve."""

    async def test_path_traversal_double_dot_raises(self, tmp_path):
        """Arrange: create storage with a base path.
        Act: attempt to resolve a key containing '../'.
        Assert: raises ValueError with 'Path traversal' message.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("../../etc/passwd")

    async def test_path_traversal_mixed_raises(self, tmp_path):
        """Arrange: create storage with a base path.
        Act: attempt a key with traversal mixed into valid segments.
        Assert: raises ValueError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            storage._resolve("col1/../etc/doc.txt")

    async def test_path_traversal_save_raises(self, tmp_path):
        """Arrange: create storage.
        Act: save with a traversal key.
        Assert: raises ValueError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            await storage.save("../../../etc/passwd", b"bad")

    async def test_path_traversal_get_raises(self, tmp_path):
        """Arrange: create storage.
        Act: get with a traversal key.
        Assert: raises ValueError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            await storage.get("../../../etc/shadow")

    async def test_path_traversal_delete_raises(self, tmp_path):
        """Arrange: create storage.
        Act: delete with a traversal key.
        Assert: raises ValueError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            await storage.delete("../../../tmp/important")

    async def test_path_traversal_exists_raises(self, tmp_path):
        """Arrange: create storage.
        Act: exists with a traversal key.
        Assert: raises ValueError.
        """
        storage = LocalStorage(str(tmp_path / "store"))

        with pytest.raises(ValueError, match="Path traversal"):
            await storage.exists("../../secret")

    async def test_valid_key_does_not_raise(self, tmp_path):
        """Arrange: create storage.
        Act: resolve a normal nested key.
        Assert: no exception is raised and the path is correct.
        """
        storage = LocalStorage(str(tmp_path / "store"))
        key = "col1/doc1/ver1/file.pdf"

        resolved = storage._resolve(key)

        assert str(resolved).startswith(str(tmp_path / "store"))