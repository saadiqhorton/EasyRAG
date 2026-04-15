# Authentication Guide

## Overview

The RAG Knowledge Base Framework uses Bearer token authentication via API keys for protected endpoints. The authentication layer is designed to:

- **Fail closed**: When `API_KEY` is configured, all protected endpoints require valid authentication
- **Allow local development**: No authentication required when `API_KEY` is not set
- **Be extensible**: Easy to add RBAC (role-based access control) in the future

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Optional* | Bearer token for API authentication |

\* Required in staging/production. Leave empty for local development.

### Generating an API Key

Generate a secure API key:

```bash
openssl rand -hex 32
```

This produces a 64-character hex string suitable for use as an API key.

## Protected Endpoints

The following endpoints require authentication when `API_KEY` is configured:

### Write Operations (Always Protected)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/collections` | POST | Create collection |
| `/api/v1/collections/{id}` | DELETE | Delete collection |
| `/api/v1/collections/{id}/documents` | POST | Upload document |
| `/api/v1/documents/{id}/replace` | POST | Replace document |
| `/api/v1/documents/{id}` | DELETE | Delete document |
| `/api/v1/collections/{id}/reindex` | POST | Reindex collection |

### Read Operations (Protected in Production)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/collections/{id}/search` | POST | Search collection |
| `/api/v1/collections/{id}/ask` | POST | Ask question |

### Public Endpoints (No Auth Required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/ready` | GET | Readiness check |
| `/api/v1/collections` | GET | List collections |
| `/api/v1/collections/{id}` | GET | Get collection details |
| `/api/v1/collections/{id}/health` | GET | Collection health |
| `/api/v1/documents/{id}` | GET | Get document details |
| `/api/v1/ingestion-jobs/{id}` | GET | Get job status |
| `/api/v1/collections/{id}/failures` | GET | List failures |
| `/api/v1/answers/{id}` | GET | Get answer |

## Using Authentication

### With cURL

Include the API key in the `Authorization` header as a Bearer token:

```bash
# Upload a document
curl -X POST http://localhost:8000/api/v1/collections/{id}/documents \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -F "file=@document.pdf"

# Search
curl -X POST http://localhost:8000/api/v1/collections/{id}/search \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query"}'

# Ask a question
curl -X POST http://localhost:8000/api/v1/collections/{id}/ask \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "your question"}'
```

### With Python (httpx)

```python
import httpx

API_KEY = "your-api-key-here"
BASE_URL = "http://localhost:8000"

def upload_document(collection_id: str, file_path: str):
    with open(file_path, 'rb') as f:
        response = httpx.post(
            f"{BASE_URL}/api/v1/collections/{collection_id}/documents",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": ("document.pdf", f, "application/pdf")},
        )
    return response.json()

def search(collection_id: str, query: str):
    response = httpx.post(
        f"{BASE_URL}/api/v1/collections/{collection_id}/search",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"query": query},
    )
    return response.json()
```

### With JavaScript (fetch)

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "http://localhost:8000";

async function uploadDocument(collectionId, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${BASE_URL}/api/v1/collections/${collectionId}/documents`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
      },
      body: formData,
    }
  );
  return response.json();
}

async function search(collectionId, query) {
  const response = await fetch(
    `${BASE_URL}/api/v1/collections/${collectionId}/search`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    }
  );
  return response.json();
}
```

## Environment-Specific Behavior

### Local Development (No Auth)

When `API_KEY` is not set:

- All endpoints are accessible without authentication
- Health checks remain public
- Suitable for local development and testing

```bash
# .env.local - no API_KEY set
POSTGRES_URL=postgresql+asyncpg://...
QDRANT_URL=http://localhost:6333
# API_KEY is not set - no auth required
```

### Staging/Production (With Auth)

When `API_KEY` is set:

- Protected endpoints require valid Bearer token
- Invalid or missing tokens return 401 Unauthorized
- Tokens are compared using timing-safe comparison

```bash
# .env.production - auth required
POSTGRES_URL=postgresql+asyncpg://...
QDRANT_URL=http://qdrant:6333
API_KEY=abc123...  # Auth now required
```

## Security Considerations

### API Key Storage

1. **Never commit API keys to version control**
2. **Use environment variables or secrets management**
3. **Rotate keys regularly** (recommended every 90 days)
4. **Use different keys for staging and production**

### HTTPS in Production

Always use HTTPS in production to prevent token interception:

```
# Production
Authorization: Bearer YOUR_API_KEY

# Sent over HTTPS - secure
```

### Rate Limiting

Consider adding rate limiting in production:

- Per-API-key request limits
- IP-based rate limiting
- Endpoint-specific limits (uploads vs reads)

## Troubleshooting

### 401 Unauthorized

**Cause**: Missing or invalid API key

**Solution**:
- Verify `API_KEY` is set in environment
- Check Authorization header format: `Bearer YOUR_KEY`
- Ensure no extra spaces or newlines in token

### 403 Forbidden (Future RBAC)

**Cause**: Valid key but insufficient permissions

**Solution**:
- Check RBAC configuration (if implemented)
- Verify key has required permissions

### Testing Authentication

Test your API key:

```bash
# Should work (if API_KEY set)
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/v1/collections

# Should fail (wrong key)
curl -H "Authorization: Bearer wrong_key" \
  http://localhost:8000/api/v1/collections
# Returns: {"detail":"Invalid API key"}
```

## Future Extensions

The authentication layer is designed to support future enhancements:

### Role-Based Access Control (RBAC)

Add roles to API keys:

```python
# Example future implementation
API_KEY_ROLES={
    "key1": ["read", "write"],
    "key2": ["read"],
}
```

### Multiple API Keys

Support multiple valid keys:

```python
API_KEYS=key1,key2,key3  # Any of these are valid
```

### Token Expiration

Implement JWT tokens with expiration:

```python
# Future: JWT tokens
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## Implementation Details

The authentication is implemented in `app/backend/services/auth.py`:

- Uses `fastapi.security.HTTPBearer` for token extraction
- Uses `secrets.compare_digest()` for timing-attack-resistant comparison
- Fails closed: requires valid token when `API_KEY` is configured
- Optional: allows unauthenticated access when `API_KEY` is not set

Protected endpoints import and use:

```python
from ..services.auth import require_auth

@router.post("/endpoint")
async def protected_endpoint(
    api_key: str = require_auth,  # Requires auth when API_KEY set
):
    ...
```
