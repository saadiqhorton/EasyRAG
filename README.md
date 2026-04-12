# RAG Knowledge Base Framework

A system that reads your documents, indexes them for fast search, and gives you answers with source citations.

## What This Project Does

This is a knowledge base platform that helps you find answers in your own documents. You upload files (PDFs, Markdown, Word docs, plain text, or HTML). The system reads them, breaks them into searchable pieces, and creates an index. When you ask a question, it finds the most relevant pieces of text and generates an answer. Every answer comes with citations so you can check where the information came from.

The system is honest about what it knows and does not know. If the evidence is weak or missing, it says so instead of making up an answer.

## Getting Started

### Requirements

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+

### Installation

1. Clone the repository
   ```bash
   cd rag-kb-project
   ```

2. Set up environment variables
   ```bash
   cp app/infra/.env.example app/infra/.env
   # Edit .env with your values
   ```

3. Start all services with Docker Compose
   ```bash
   cd app/infra
   docker compose up -d
   ```

4. The API will be available at http://localhost:8000
5. The frontend will be available at http://localhost:3000

### Running Without Docker

**Backend:**
```bash
cd app/backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.backend.main:app --reload
```

**Frontend:**
```bash
cd app/frontend
npm install
npm run dev
```

**Worker:**
```bash
cd app/backend
python -m workers.ingestion_worker
```

## How to Use

1. **Create a collection** - A collection groups related documents together
2. **Upload documents** - Drag and drop files into the collection
3. **Wait for indexing** - The worker processes your files automatically
4. **Ask questions** - Type a question and get an answer with citations
5. **Check evidence** - Click on citations to see the source text

## Project Structure

```
app/
├── backend/              # Python FastAPI backend
│   ├── api/              # API endpoints (collections, documents, search)
│   ├── models/           # Database models and schemas
│   ├── services/         # Business logic (parsing, chunking, retrieval, generation)
│   ├── workers/          # Background job processor
│   ├── prompts/          # LLM prompt templates
│   └── tests/            # Unit and integration tests
├── frontend/             # Next.js 15 frontend
│   ├── app/              # Pages and layouts
│   ├── components/       # UI components
│   └── lib/              # API client, types, utilities
└── infra/                # Docker Compose and environment config
```

## API Reference

**Base URL:** `http://localhost:8000/api/v1`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/collections` | POST | Create a new collection |
| `/collections` | GET | List all collections |
| `/collections/{id}` | GET | Get collection details |
| `/collections/{id}` | DELETE | Delete a collection |
| `/collections/{id}/documents` | POST | Upload a document |
| `/collections/{id}/documents` | GET | List documents in collection |
| `/collections/{id}/search` | POST | Search for relevant chunks |
| `/collections/{id}/ask` | POST | Ask a question with generation |
| `/documents/{id}` | GET | Get document details |
| `/documents/{id}/replace` | POST | Upload a new version |
| `/documents/{id}` | DELETE | Delete a document |
| `/collections/{id}/failures` | GET | View ingestion failures |
| `/answers/{id}` | GET | Get a past answer |
| `/health` | GET | Service health check |
| `/health/ready` | GET | Readiness check (DB + Qdrant) |

## Running Tests

**Backend:**
```bash
cd app/backend
pip install -e ".[dev]"
pytest
```

**Frontend:**
```bash
cd app/frontend
npm install
npm run test
```

## Key Design Decisions

- **Hybrid retrieval** uses both semantic search and keyword matching. This finds more relevant results than either method alone.
- **Grounded answers** only use text from your documents. The system never invents information.
- **Abstention** means the system refuses to answer when evidence is too weak. This prevents false answers.
- **Version tracking** keeps history when you replace a document. Old versions are marked as superseded.
- **Failure visibility** means you can always see what went wrong during document processing.