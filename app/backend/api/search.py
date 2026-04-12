"""Search and Ask API endpoints for retrieval and answer generation."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.answer_record import AnswerRecord
from ..models.query_session import QuerySession
from ..models.schemas import (
    AnswerResponse,
    AskRequest,
    AskResponse,
    Citation,
    EvidenceItem,
    ScoredChunk,
    SearchRequest,
    SearchResponse,
)
from ..services.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collections/{collection_id}/search", response_model=SearchResponse)
async def search_collection(
    collection_id: uuid.UUID,
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Search a collection for relevant chunks (retrieval only, no generation)."""
    try:
        from ..services.query_normalizer import normalize_query
        from ..services.retriever import deduplicate_candidates, hybrid_search
        from ..services.reranker import rerank_candidates

        query_ctx = normalize_query(request.query, collection_id)
        candidates = await hybrid_search(query_ctx, top_k=request.limit)
        candidates = deduplicate_candidates(candidates)
        reranked, _reranker_used = rerank_candidates(
            query_ctx.raw_query, candidates, top_k=request.limit
        )

        results = [
            ScoredChunk(
                chunk_id=_to_uuid(c.chunk_id),
                score=c.score,
                text=c.text_content,
                title=c.title or None,
                section_path=c.section_path or None,
                page_number=c.page_number,
                modality=c.modality,
                confidence=c.confidence,
                document_id=_to_uuid(c.document_id),
                version_id=_to_uuid(c.version_id),
                collection_id=collection_id,
            )
            for c in reranked
        ]

        return SearchResponse(results=results)
    except Exception as e:
        logger.error(
            "search_error collection_id=%s error=%s",
            collection_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Error processing search"
        ) from e


@router.post("/collections/{collection_id}/ask", response_model=AskResponse)
async def ask_collection(
    collection_id: uuid.UUID,
    request: AskRequest,
    session: AsyncSession = Depends(get_session),
) -> AskResponse:
    """Ask a question against a collection (full pipeline with generation)."""
    try:
        from ..services.evidence import package_evidence
        from ..services.generator import generate_answer
        from ..services.query_normalizer import normalize_query
        from ..services.reranker import rerank_candidates
        from ..services.retriever import deduplicate_candidates, hybrid_search

        # Create query session
        query_ctx = normalize_query(request.query, collection_id)
        q_session = QuerySession(
            collection_id=collection_id,
            raw_query=query_ctx.raw_query,
            normalized_query=query_ctx.normalized_query,
        )
        session.add(q_session)
        await session.flush()

        # Hybrid retrieval
        candidates = await hybrid_search(query_ctx, top_k=20)
        candidates = deduplicate_candidates(candidates)

        # Rerank
        reranked, reranker_used = rerank_candidates(
            query_ctx.raw_query, candidates, top_k=5
        )

        # Package evidence
        evidence_pkg = package_evidence(reranked)

        # Generate answer
        answer_result = await generate_answer(
            query=query_ctx.raw_query,
            evidence=evidence_pkg,
            reranker_used=reranker_used,
        )

        # Store answer record
        evidence_ids = [str(e.chunk_id) for e in evidence_pkg.items]
        citations_json_data = [
            {
                "source_number": c.source_number,
                "document_title": c.document_title,
                "section_path": c.section_path,
                "page_number": c.page_number,
                "chunk_id": str(c.chunk_id),
            }
            for c in answer_result.citations
        ]

        raw_scores = [
            {"chunk_id": getattr(c, "chunk_id", ""), "score": c.score}
            for c in candidates[:20]
        ]

        answer_record = AnswerRecord(
            session_id=q_session.id,
            collection_id=collection_id,
            answer_text=answer_result.answer_text,
            answer_mode=answer_result.answer_mode,
            citations_json=json.dumps(citations_json_data),
            evidence_ids_json=json.dumps(evidence_ids),
            raw_candidate_scores_json=json.dumps(raw_scores),
            reranker_used=reranker_used,
            llm_model=answer_result.llm_model,
            latency_ms=answer_result.latency_ms,
        )
        session.add(answer_record)
        await session.flush()

        return AskResponse(
            answer_id=answer_record.id,
            answer_text=answer_result.answer_text,
            answer_mode=answer_result.answer_mode,
            citations=answer_result.citations,
            evidence=evidence_pkg.items,
        )
    except Exception as e:
        logger.error(
            "ask_error collection_id=%s error=%s",
            collection_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Error processing question"
        ) from e


@router.get("/answers/{answer_id}", response_model=AnswerResponse)
async def get_answer(
    answer_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    """Retrieve a past answer with its full evidence."""
    record = await session.get(AnswerRecord, answer_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Answer not found")

    citations_data = (
        json.loads(record.citations_json) if record.citations_json else []
    )
    citations = [
        Citation(
            source_number=c.get("source_number", 0),
            document_title=c.get("document_title", ""),
            section_path=c.get("section_path"),
            page_number=c.get("page_number"),
            chunk_id=_to_uuid(c.get("chunk_id", str(uuid.uuid4()))),
        )
        for c in citations_data
    ]

    evidence_ids = (
        json.loads(record.evidence_ids_json) if record.evidence_ids_json else []
    )
    evidence_items = [
        EvidenceItem(
            chunk_id=_to_uuid(eid) if isinstance(eid, str) else eid,
            document_id=uuid.uuid4(),
            document_title="",
            text="",
            modality="text",
            confidence=0.0,
            citation_anchor="",
            ocr_used=False,
        )
        for eid in evidence_ids
    ]

    return AnswerResponse(
        id=record.id,
        session_id=record.session_id,
        collection_id=record.collection_id,
        answer_text=record.answer_text,
        answer_mode=record.answer_mode,
        citations=citations,
        evidence=evidence_items,
        reranker_used=record.reranker_used,
        llm_model=record.llm_model,
        latency_ms=record.latency_ms,
        created_at=record.created_at,
    )


def _to_uuid(value: str) -> uuid.UUID:
    """Safely convert a string to UUID, returning a nil UUID on failure."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        logger.warning("invalid_uuid value=%s, using nil UUID", value)
        return uuid.UUID(int=0)