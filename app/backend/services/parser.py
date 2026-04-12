"""Docling-based document parser with OCR fallback and confidence tracking."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from datetime import UTC, datetime

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "text/markdown": InputFormat.MARKDOWN,
    "text/x-markdown": InputFormat.MARKDOWN,
    "application/pdf": InputFormat.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": InputFormat.DOCX,
    "text/plain": InputFormat.MARKDOWN,
    "text/html": InputFormat.HTML,
}

OCR_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class ParseResult:
    """Structured output from the parser."""

    title: str
    text_content: str
    sections: list[dict] = field(default_factory=list)
    page_mapping: dict[int, str] = field(default_factory=dict)
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    modality: str = "text"
    normalized_markdown: str = ""
    normalized_json: str = ""
    page_count: int | None = None


def _build_converter() -> DocumentConverter:
    """Build a Docling DocumentConverter with OCR fallback for PDFs."""
    pdf_options = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
        }
    )


def _extract_sections(doc) -> list[dict]:
    """Extract sections from DoclingDocument with heading paths."""
    sections = []
    for item in doc.iterate_items():
        if hasattr(item, "heading") and item.heading:
            sections.append({
                "heading": item.heading,
                "level": getattr(item, "level", 1),
                "text": getattr(item, "text", ""),
            })
    return sections


def _build_page_mapping(doc) -> dict[int, str]:
    """Build a mapping from page number to text content."""
    mapping: dict[int, str] = {}
    for item in doc.iterate_items():
        page = getattr(item, "page", None) or getattr(item, "prov", [{}])
        if isinstance(page, list) and page:
            page_no = page[0].get("page_no", 1)
        elif isinstance(page, int):
            page_no = page
        else:
            page_no = 1
        mapping.setdefault(page_no, "")
        text = getattr(item, "text", "")
        if text:
            mapping[page_no] += text + "\n"
    return mapping


def _estimate_confidence(doc, mime_type: str) -> float:
    """Estimate parse confidence based on OCR usage and content quality."""
    if mime_type == "application/pdf":
        ocr_used = getattr(doc, "ocr_used", False)
        if ocr_used:
            return OCR_CONFIDENCE_THRESHOLD
    return 1.0


async def parse_document(file_path: str, mime_type: str) -> ParseResult:
    """Parse a document file into a normalized representation.

    Args:
        file_path: Absolute path to the document file.
        mime_type: MIME type of the document.

    Returns:
        ParseResult with extracted content, sections, and confidence.

    Raises:
        ValueError: If the MIME type is not supported.
        RuntimeError: If parsing fails.
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    converter = _build_converter()
    input_format = ALLOWED_MIME_TYPES[mime_type]

    try:
        result = converter.convert(Path(file_path))
        doc = result.document
    except Exception as e:
        logger.error("parse_failed file=%s error=%s", file_path, e)
        raise RuntimeError(f"Parse failed: {e}") from e

    warnings = []
    for w in getattr(result, "warnings", []):
        warnings.append(str(w))

    # Extract structured content
    markdown_output = doc.export_to_markdown()
    title = doc.title if doc.title else Path(file_path).stem
    sections = _extract_sections(doc)
    page_mapping = _build_page_mapping(doc)
    confidence = _estimate_confidence(doc, mime_type)

    # Flag low-confidence OCR
    ocr_derived = confidence < 1.0
    if ocr_derived:
        warnings.append(
            f"OCR-derived text with confidence {confidence:.2f}. "
            "Content may contain errors."
        )

    page_count = len(page_mapping) if page_mapping else None

    # Build JSON representation
    json_output = doc.export_to_dict() if hasattr(doc, "export_to_dict") else ""

    return ParseResult(
        title=title,
        text_content=markdown_output,
        sections=sections,
        page_mapping=page_mapping,
        confidence=confidence,
        warnings=warnings,
        modality="ocr_text" if ocr_derived else "text",
        normalized_markdown=markdown_output,
        normalized_json=str(json_output),
        page_count=page_count,
    )