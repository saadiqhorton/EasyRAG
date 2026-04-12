"""Root router aggregating all sub-routers, mounted at /api/v1."""

from fastapi import APIRouter

from .collections import router as collections_router
from .document_management import router as document_management_router
from .documents import router as documents_router
from .ingestion import router as ingestion_router
from .search import router as search_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(collections_router, tags=["collections"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(document_management_router, tags=["document-management"])
api_router.include_router(ingestion_router, tags=["ingestion"])
api_router.include_router(search_router, tags=["search"])