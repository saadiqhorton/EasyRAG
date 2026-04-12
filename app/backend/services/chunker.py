"""Structure-aware chunking service that preserves document hierarchy."""

import logging
import re
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Rough token estimation: 1 token ~ 4 characters for English text
CHARS_PER_TOKEN = 4


@dataclass
class ChunkData:
    """A chunk ready for database insertion."""

    id: uuid.UUID
    collection_id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    order_index: int
    title: str | None
    section_path: str | None
    page_number_start: int | None
    page_number_end: int | None
    modality: str
    confidence: float
    token_count: int
    text_content: str


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _split_at_boundary(
    text: str, max_tokens: int
) -> list[str]:
    """Split text at paragraph boundaries to fit max_tokens."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_tokens = _estimate_tokens(para)

        if para_tokens > max_tokens:
            # Flush current buffer
            if current:
                chunks.append(current.strip())
                current = ""
            # Split long paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                sent_tokens = _estimate_tokens(sent)
                if _estimate_tokens(current) + sent_tokens > max_tokens:
                    if current:
                        chunks.append(current.strip())
                    current = sent
                else:
                    current = current + " " + sent if current else sent
        elif _estimate_tokens(current) + para_tokens > max_tokens:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


def _add_overlap(chunks: list[str], overlap_tokens: int) -> list[str]:
    """Add overlapping text between consecutive chunks."""
    if overlap_tokens <= 0 or len(chunks) <= 1:
        return chunks

    overlapped = [chunks[0]]
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    for i in range(1, len(chunks)):
        prev_text = chunks[i - 1]
        overlap_text = prev_text[-overlap_chars:] if len(prev_text) > overlap_chars else prev_text
        overlapped.append(overlap_text + "\n\n" + chunks[i])

    return overlapped


def chunk_document(
    text_content: str,
    sections: list[dict],
    page_mapping: dict[int, str],
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    confidence: float,
    modality: str,
    max_tokens: int = 500,
    overlap_tokens: int = 150,
    title: str | None = None,
) -> list[ChunkData]:
    """Chunk a parsed document into structured segments.

    Args:
        text_content: Full document text.
        sections: Parsed sections with headings.
        page_mapping: Page number to text mapping.
        collection_id: UUID of the collection.
        document_id: UUID of the source document.
        version_id: UUID of the document version.
        confidence: Parse confidence score.
        modality: Text modality (text, ocr_text).
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Overlap tokens between chunks.
        title: Document title.

    Returns:
        List of ChunkData objects ready for insertion.
    """
    chunks: list[ChunkData] = []
    order_index = 0

    if sections:
        # Section-aware chunking: process each section
        current_section_path = ""
        current_page = None

        for section in sections:
            heading = section.get("heading", "")
            level = section.get("level", 1)
            text = section.get("text", "")

            # Build section path
            if heading:
                current_section_path = heading

            if not text.strip():
                continue

            # Determine page number from page mapping
            for page_no, page_text in page_mapping.items():
                if text[:50] in page_text:
                    current_page = page_no
                    break

            section_chunks = _split_at_boundary(text, max_tokens)
            section_chunks = _add_overlap(section_chunks, overlap_tokens)

            for chunk_text in section_chunks:
                chunks.append(
                    ChunkData(
                        id=uuid.uuid4(),
                        collection_id=collection_id,
                        document_id=document_id,
                        version_id=version_id,
                        order_index=order_index,
                        title=title,
                        section_path=current_section_path,
                        page_number_start=current_page,
                        page_number_end=current_page,
                        modality=modality,
                        confidence=confidence,
                        token_count=_estimate_tokens(chunk_text),
                        text_content=chunk_text,
                    )
                )
                order_index += 1
    else:
        # Fallback: chunk the full text content
        text_chunks = _split_at_boundary(text_content, max_tokens)
        text_chunks = _add_overlap(text_chunks, overlap_tokens)

        # Estimate page ranges from page mapping
        pages = sorted(page_mapping.keys()) if page_mapping else []

        for chunk_text in text_chunks:
            page_start = pages[0] if pages else None
            page_end = pages[-1] if pages else None

            # Try to find more specific page
            for page_no in pages:
                if chunk_text[:50] in page_mapping[page_no]:
                    page_start = page_no
                    page_end = page_no
                    break

            chunks.append(
                ChunkData(
                    id=uuid.uuid4(),
                    collection_id=collection_id,
                    document_id=document_id,
                    version_id=version_id,
                    order_index=order_index,
                    title=title,
                    section_path=None,
                    page_number_start=page_start,
                    page_number_end=page_end,
                    modality=modality,
                    confidence=confidence,
                    token_count=_estimate_tokens(chunk_text),
                    text_content=chunk_text,
                )
            )
            order_index += 1

    logger.info(
        "chunked document=%s chunks=%d tokens_avg=%d",
        document_id, len(chunks),
        sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks