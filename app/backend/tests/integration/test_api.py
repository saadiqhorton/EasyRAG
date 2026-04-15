"""Integration tests for FastAPI endpoints using httpx AsyncClient.

Tests exercise the full request/response cycle through the ASGI transport
with an in-memory SQLite database, a mocked Qdrant client, and a mocked
object-storage backend.  No external services are required.
"""

import uuid

from httpx import AsyncClient


# ======================================================================
# Health / readiness
# ======================================================================


async def test_health_endpoint(client: AsyncClient) -> None:
    """GET /health returns 200 with status=healthy and the current version."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


async def test_readiness_endpoint(client: AsyncClient) -> None:
    """GET /health/ready returns 200 when both postgres and qdrant are reachable."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["postgres"] is True
    assert body["qdrant"] is True


# ======================================================================
# Collection CRUD
# ======================================================================


async def test_create_collection(client: AsyncClient) -> None:
    """POST /api/v1/collections creates a new collection and returns 201."""
    payload = {"name": "Integration Test Collection", "description": "Created by integration test"}
    response = await client.post("/api/v1/collections", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Integration Test Collection"
    assert body["description"] == "Created by integration test"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body
    assert body["document_count"] == 0


async def test_create_collection_minimal(client: AsyncClient) -> None:
    """POST /api/v1/collections works with only the required name field."""
    payload = {"name": "Minimal Collection"}
    response = await client.post("/api/v1/collections", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Minimal Collection"
    assert body["description"] is None


async def test_list_collections_empty(client: AsyncClient) -> None:
    """GET /api/v1/collections returns an empty list when no collections exist."""
    response = await client.get("/api/v1/collections")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_collections_after_create(client: AsyncClient) -> None:
    """GET /api/v1/collections returns collections that were created."""
    # Create two collections
    await client.post("/api/v1/collections", json={"name": "Alpha"})
    await client.post("/api/v1/collections", json={"name": "Beta"})

    response = await client.get("/api/v1/collections")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    names = {c["name"] for c in body}
    assert names == {"Alpha", "Beta"}


async def test_list_collections_pagination(client: AsyncClient) -> None:
    """GET /api/v1/collections respects skip and limit query parameters."""
    for i in range(5):
        await client.post("/api/v1/collections", json={"name": f"Page-{i}"})

    # First page of 2
    resp = await client.get("/api/v1/collections", params={"skip": 0, "limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Second page of 2
    resp = await client.get("/api/v1/collections", params={"skip": 2, "limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Remaining page
    resp = await client.get("/api/v1/collections", params={"skip": 4, "limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_get_collection_detail(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id} returns detailed information about a collection."""
    create_resp = await client.post(
        "/api/v1/collections",
        json={"name": "Detail Test", "description": "For detail endpoint"},
    )
    collection_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/collections/{collection_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == collection_id
    assert body["name"] == "Detail Test"
    assert body["description"] == "For detail endpoint"
    assert body["document_count"] == 0
    # Detail response includes extra fields
    assert "health" in body
    assert "recent_failures" in body


async def test_get_collection_not_found(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id} returns 404 for a non-existent collection."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/collections/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_get_collection_invalid_id(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id} returns 422 for an invalid UUID."""
    response = await client.get("/api/v1/collections/not-a-uuid")
    assert response.status_code == 422


async def test_delete_collection(client: AsyncClient) -> None:
    """DELETE /api/v1/collections/{id} removes the collection and returns a confirmation."""
    create_resp = await client.post(
        "/api/v1/collections",
        json={"name": "To Delete"},
    )
    collection_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/collections/{collection_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    # Confirm the collection is gone
    get_resp = await client.get(f"/api/v1/collections/{collection_id}")
    assert get_resp.status_code == 404


async def test_delete_collection_not_found(client: AsyncClient) -> None:
    """DELETE /api/v1/collections/{id} returns 404 for a non-existent collection."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(f"/api/v1/collections/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ======================================================================
# Document upload
# ======================================================================


async def test_upload_document(client: AsyncClient) -> None:
    """POST /api/v1/collections/{id}/documents uploads a text file successfully."""
    # Create a collection first
    create_resp = await client.post(
        "/api/v1/collections",
        json={"name": "Upload Target"},
    )
    collection_id = create_resp.json()["id"]

    # Upload a plain-text document
    files = {"file": ("notes.txt", b"Hello integration test", "text/plain")}
    upload_resp = await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files=files,
    )
    assert upload_resp.status_code == 201
    body = upload_resp.json()
    assert "document_id" in body
    assert "version_id" in body
    assert "job_id" in body
    assert body["title"] == "notes.txt"
    assert body["mime_type"] == "text/plain"
    assert body["file_size_bytes"] == 22  # len(b"Hello integration test")


async def test_upload_document_markdown(client: AsyncClient) -> None:
    """POST .../documents accepts markdown MIME type."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "MD Upload"},
    )
    collection_id = create_resp.json()["id"]

    files = {"file": ("readme.md", b"# Title\nParagraph", "text/markdown")}
    upload_resp = await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files=files,
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()["mime_type"] == "text/markdown"


async def test_upload_document_pdf_mime_type(client: AsyncClient) -> None:
    """POST .../documents accepts application/pdf MIME type."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "PDF Upload"},
    )
    collection_id = create_resp.json()["id"]

    files = {"file": ("paper.pdf", b"%PDF-1.4 fake", "application/pdf")}
    upload_resp = await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files=files,
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()["mime_type"] == "application/pdf"


async def test_upload_document_invalid_mime_type(client: AsyncClient) -> None:
    """POST .../documents rejects an unsupported MIME type with 400."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "Bad MIME"},
    )
    collection_id = create_resp.json()["id"]

    files = {"file": ("image.png", b"\x89PNG...", "image/png")}
    upload_resp = await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files=files,
    )
    assert upload_resp.status_code == 400
    assert "Invalid MIME type" in upload_resp.json()["detail"]


async def test_upload_document_collection_not_found(client: AsyncClient) -> None:
    """POST .../documents returns 404 when the collection does not exist."""
    fake_id = str(uuid.uuid4())
    files = {"file": ("notes.txt", b"content", "text/plain")}
    upload_resp = await client.post(
        f"/api/v1/collections/{fake_id}/documents",
        files=files,
    )
    assert upload_resp.status_code == 404
    assert "not found" in upload_resp.json()["detail"].lower()


# ======================================================================
# Document listing
# ======================================================================


async def test_list_documents_empty(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id}/documents returns empty items when no documents exist."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "Empty Docs"},
    )
    collection_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/collections/{collection_id}/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_documents_after_upload(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id}/documents returns uploaded documents."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "Has Docs"},
    )
    collection_id = create_resp.json()["id"]

    # Upload two documents
    await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files={"file": ("a.txt", b"aaa", "text/plain")},
    )
    await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files={"file": ("b.txt", b"bbb", "text/plain")},
    )

    resp = await client.get(f"/api/v1/collections/{collection_id}/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    filenames = {item["original_filename"] for item in body["items"]}
    assert filenames == {"a.txt", "b.txt"}


# ======================================================================
# Document detail
# ======================================================================


async def test_get_document_detail(client: AsyncClient) -> None:
    """GET /api/v1/documents/{id} returns document details including versions."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "Doc Detail"},
    )
    collection_id = create_resp.json()["id"]

    upload_resp = await client.post(
        f"/api/v1/collections/{collection_id}/documents",
        files={"file": ("detail.txt", b"detail content", "text/plain")},
    )
    document_id = upload_resp.json()["document_id"]

    resp = await client.get(f"/api/v1/documents/{document_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == document_id
    assert body["title"] == "detail.txt"
    assert body["mime_type"] == "text/plain"
    assert "versions" in body
    assert len(body["versions"]) == 1
    assert body["active_version"]["is_active"] is True


async def test_get_document_not_found(client: AsyncClient) -> None:
    """GET /api/v1/documents/{id} returns 404 for a non-existent document."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/documents/{fake_id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ======================================================================
# Collection health sub-resource
# ======================================================================


async def test_get_collection_health(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id}/health returns health statistics."""
    create_resp = await client.post(
        "/api/v1/collections", json={"name": "Health Check"},
    )
    collection_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/collections/{collection_id}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_documents"] == 0
    assert body["indexed_count"] == 0
    assert body["failed_count"] == 0


async def test_get_collection_health_not_found(client: AsyncClient) -> None:
    """GET /api/v1/collections/{id}/health returns 404 for a missing collection."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/collections/{fake_id}/health")
    assert resp.status_code == 404