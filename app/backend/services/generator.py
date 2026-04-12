"""Grounded answer generation with abstention logic and retry."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass

import httpx

from .config import get_settings
from .evidence import EvidencePackage
from ..models.schemas import Citation, EvidenceItem
from ..prompts.grounded_answer import (
    ABSTENTION_RESPONSE,
    GROUNDED_ANSWER_SYSTEM_PROMPT,
    GROUNDED_ANSWER_USER_TEMPLATE,
    build_evidence_text,
)

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Answer modes
ANSWERED_WITH_EVIDENCE = "answered_with_evidence"
PARTIALLY_ANSWERED = "partially_answered_with_caveat"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass
class GeneratedAnswer:
    """Result of the answer generation pipeline."""

    answer_text: str
    answer_mode: str
    citations: list[Citation]
    evidence_ids: list[str]
    llm_model: str
    reranker_used: bool
    latency_ms: int
    raw_candidate_scores: list[dict] | None = None


def _should_abstain(evidence: EvidencePackage, score_threshold: float) -> bool:
    """Determine if the system should abstain from answering.

    Abstain when:
    - Average retrieval score is below threshold
    - Only low-confidence OCR evidence is available
    """
    if evidence.average_score < score_threshold:
        logger.info("abstaining: low_score=%.3f", evidence.average_score)
        return True

    all_low_confidence = all(
        item.confidence < 0.5 for item in evidence.items
    )
    if all_low_confidence and evidence.items:
        logger.info("abstaining: all_low_confidence_ocr")
        return True

    return False


def _determine_mode(evidence: EvidencePackage, score_threshold: float) -> str:
    """Determine the answer mode based on evidence quality."""
    if _should_abstain(evidence, score_threshold):
        return INSUFFICIENT_EVIDENCE

    if evidence.has_low_confidence or evidence.average_score < score_threshold * 1.5:
        return PARTIALLY_ANSWERED

    return ANSWERED_WITH_EVIDENCE


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the OpenAI-compatible LLM API with retry.

    Implements: retry with exponential backoff for transient errors,
    defensive response validation, and graceful error handling.
    """
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.answer_llm_api_key:
        headers["Authorization"] = f"Bearer {settings.answer_llm_api_key}"

    payload = {
        "model": settings.answer_llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    content = ""
    for attempt in range(1 + _MAX_RETRIES):
        if attempt > 0:
            await asyncio.sleep(_RETRY_DELAY_SECONDS * attempt)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.answer_llm_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    if attempt == _MAX_RETRIES:
                        resp.raise_for_status()
                    continue
                resp.raise_for_status()

                data = resp.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                break
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                logger.warning("llm_rate_limited status=%d", status)
            elif status >= 500:
                logger.warning("llm_server_error status=%d", status)
            else:
                logger.warning("llm_client_error status=%d", status)
            if status in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                continue
            raise
        except httpx.TimeoutException:
            logger.warning("llm_timeout attempt=%d", attempt)
            if attempt < _MAX_RETRIES:
                continue
            raise
        except httpx.ConnectError:
            logger.warning("llm_connect_error attempt=%d", attempt)
            if attempt < _MAX_RETRIES:
                continue
            raise

    if not content.strip():
        raise ValueError("LLM returned empty content")

    return content


async def generate_answer(
    query: str,
    evidence: EvidencePackage,
    reranker_used: bool = True,
) -> GeneratedAnswer:
    """Generate a grounded answer from evidence with abstention logic.

    Args:
        query: The user's question.
        evidence: Packaged evidence from retrieval.
        reranker_used: Whether the reranker was applied.

    Returns:
        GeneratedAnswer with answer text, mode, citations, and metadata.
    """
    settings = get_settings()
    start = time.time()

    mode = _determine_mode(evidence, settings.abstention_score_threshold)

    if mode == INSUFFICIENT_EVIDENCE:
        elapsed = int((time.time() - start) * 1000)
        logger.info("answer_abstained query=%s", query[:50])
        return GeneratedAnswer(
            answer_text=ABSTENTION_RESPONSE,
            answer_mode=mode,
            citations=[],
            evidence_ids=[str(item.chunk_id) for item in evidence.items],
            llm_model=settings.answer_llm_model,
            reranker_used=reranker_used,
            latency_ms=elapsed,
        )

    # Build evidence text for prompt
    evidence_dicts = [
        {
            "text_content": item.text,
            "document_title": item.document_title,
            "section_path": item.section_path,
            "page_number": item.page_number,
            "modality": item.modality,
            "confidence": item.confidence,
        }
        for item in evidence.items
    ]
    evidence_text = build_evidence_text(evidence_dicts)
    user_prompt = GROUNDED_ANSWER_USER_TEMPLATE.format(
        query=query, evidence_text=evidence_text
    )

    # Call LLM with retry
    try:
        answer_text = await _call_llm(GROUNDED_ANSWER_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("llm_failed, using evidence-only fallback: %s", e)
        bullets = []
        for item in evidence.items:
            source = item.document_title
            if item.page_number:
                source += f" (p. {item.page_number})"
            bullets.append(f"- [{source}] {item.text[:200]}")
        answer_text = (
            "Could not generate an answer. "
            "Here is the retrieved evidence:\n\n"
            + "\n".join(bullets)
        )
        mode = PARTIALLY_ANSWERED

    elapsed = int((time.time() - start) * 1000)

    # Build Citation schema objects
    citations = [
        Citation(
            source_number=c.index,
            document_title=c.document_title,
            section_path=c.section_path,
            page_number=c.page_number,
            chunk_id=uuid.UUID(c.chunk_id) if _is_valid_uuid(c.chunk_id) else uuid.UUID(int=0),
        )
        for c in evidence.citations
    ]

    logger.info(
        "answer_generated mode=%s latency_ms=%d citations=%d",
        mode, elapsed, len(citations),
    )

    return GeneratedAnswer(
        answer_text=answer_text,
        answer_mode=mode,
        citations=citations,
        evidence_ids=[str(item.chunk_id) for item in evidence.items],
        llm_model=settings.answer_llm_model,
        reranker_used=reranker_used,
        latency_ms=elapsed,
    )


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False