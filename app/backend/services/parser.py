"""Docling-based document parser with OCR fallback and confidence tracking."""

import asyncio
import logging
import signal
from dataclasses import dataclass, field
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

from .constants import OCR_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# Safety limits for parsing
PARSE_TIMEOUT_SECONDS = 120  # Max time for a single parse operation
MAX_PARSE_FILE_SIZE_MB = 100  # Max file size to attempt parsing

ALLOWED_MIME_TYPES = {
    "text/markdown": InputFormat.MD,
    "text/x-markdown": InputFormat.MD,
    "application/pdf": InputFormat.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": InputFormat.DOCX,
    "text/plain": InputFormat.MD,
    "text/html": InputFormat.HTML,
}


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
    """Extract sections from DoclingDocument with heading paths.

    Docling's iterate_items() yields (item, level) tuples.
    Items have a label attribute indicating their type (section header,
    paragraph, list, etc.) and text content.
    """
    sections = []
    for item, level in doc.iterate_items():
        label = str(getattr(item, "label", "")).lower()
        text = getattr(item, "text", "")

        # Check if this is a heading/section header
        is_heading = (
            "heading" in label
            or "section" in label
            or "title" in label
            or "header" in label
        )

        # Also treat as heading if the text looks like a heading
        # (short text, not ending with period, etc.)
        if text and not text.endswith((".", "!", "?")) and len(text) < 120:
            is_heading = is_heading or len(text.split()) <= 10

        if text and text.strip():
            sections.append({
                "heading": text.strip() if is_heading else "",
                "level": level if isinstance(level, int) else 1,
                "text": text.strip(),
            })
    return sections


def _build_page_mapping(doc) -> dict[int, str]:
    """Build a mapping from page number to text content.

    Docling items may carry provenance info with page numbers.
    Falls back to page 1 if no page info is available.
    """
    mapping: dict[int, str] = {}
    for item, level in doc.iterate_items():
        page_no = 1  # default

        # Try multiple ways to get page number from Docling items
        prov = getattr(item, "prov", None)
        if prov and isinstance(prov, list) and len(prov) > 0:
            # Docling stores provenance as a list of dicts with page_no
            page_no = prov[0].get("page_no", 1)
        else:
            # Try direct page attribute
            page_attr = getattr(item, "page", None)
            if isinstance(page_attr, int):
                page_no = page_attr

        mapping.setdefault(page_no, "")
        text = getattr(item, "text", "")
        if text:
            mapping[page_no] += text + "\n"
    return mapping


def _estimate_confidence(doc, mime_type: str) -> float:
    """Estimate parse confidence based on OCR usage and content quality.

    For PDFs, checks whether OCR was applied by inspecting the conversion
    result metadata. Docling sets OCR info on the input document or
    pipeline options rather than the output, so we use heuristics:
    check the conversion status for OCR indicators.
    """
    if mime_type == "application/pdf":
        # Docling tracks OCR usage in the conversion result.
        # The result object (not the doc) has status information.
        # We check the document pages for OCR indicators.
        # A low-confidence PDF will often have short, garbled text
        # or text that looks like OCR output.
        text_content = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else ""

        # Heuristic: if the PDF text is very short relative to typical
        # PDF content, OCR may have been needed but partially failed.
        # Also check for OCR-like artifacts (common OCR errors).
        if len(text_content.strip()) == 0:
            return 0.3  # Empty extraction - likely scanned with no OCR

        # Check for common OCR artifact patterns that indicate low confidence
        ocr_artifact_count = 0
        ocr_artifacts = ["l1", "0O", "rn", "cl", "vv", "lI"]
        for artifact in ocr_artifacts:
            ocr_artifact_count += text_content.count(artifact)

        # If OCR artifacts are common relative to text length, lower confidence
        if len(text_content) > 0 and ocr_artifact_count / len(text_content) > 0.01:
            return OCR_CONFIDENCE_THRESHOLD

    return 1.0


def _convert_sync(converter: DocumentConverter, file_path: str):
    """Run Docling conversion synchronously (called from thread pool)."""
    return converter.convert(Path(file_path))


async def parse_document(file_path: str, mime_type: str) -> ParseResult:
    """Parse a document file into a normalized representation.

    Applies timeout and file-size guards to prevent runaway resource usage.
    Parsing runs in a thread pool with a configurable timeout.

    Args:
        file_path: Absolute path to the document file.
        mime_type: MIME type of the document.

    Returns:
        ParseResult with extracted content, sections, and confidence.

    Raises:
        ValueError: If the MIME type is not supported or file exceeds size limit.
        RuntimeError: If parsing fails or times out.
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    # File size guard
    file_size = Path(file_path).stat().st_size
    max_bytes = MAX_PARSE_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise ValueError(
            f"File too large for parsing: {file_size / 1024 / 1024:.1f}MB. "
            f"Maximum: {MAX_PARSE_FILE_SIZE_MB}MB."
        )

    converter = _build_converter()
    input_format = ALLOWED_MIME_TYPES[mime_type]

    try:
        # Run Docling conversion in a thread pool with timeout.
        # Docling is CPU-bound and synchronous, so we use run_in_executor
        # to avoid blocking the event loop and to enforce a timeout.
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                _convert_sync,
                converter,
                file_path,
            ),
            timeout=PARSE_TIMEOUT_SECONDS,
        )
        doc = result.document
    except asyncio.TimeoutError:
        logger.error(
            "parse_timeout file=%s timeout=%ds",
            file_path, PARSE_TIMEOUT_SECONDS,
        )
        raise RuntimeError(
            f"Parse timed out after {PARSE_TIMEOUT_SECONDS}s. "
            f"File may be too complex or corrupted."
        )
    except Exception as e:
        logger.error("parse_failed file=%s error=%s", file_path, e)
        raise RuntimeError(f"Parse failed: {e}") from e

    warnings = []
    for w in getattr(result, "warnings", []):
        warnings.append(str(w))

    # Extract structured content
    markdown_output = doc.export_to_markdown()

    # Extract title: try first heading line from markdown, else fall back to filename
    title = Path(file_path).stem
    for line in markdown_output.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            break

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