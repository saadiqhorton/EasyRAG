"""Shared constants for the RAG Knowledge Base application."""

# Supported MIME types for document upload and parsing
ALLOWED_MIME_TYPES: set[str] = {
    "text/markdown",
    "text/x-markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/html",
}

# Map MIME types to friendly labels for display
MIME_TYPE_LABELS: dict[str, str] = {
    "text/markdown": "Markdown",
    "text/x-markdown": "Markdown",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "text/plain": "Plain Text",
    "text/html": "HTML",
}

# Maximum upload size in bytes (50 MB default)
MAX_UPLOAD_SIZE_MB = 50

# OCR confidence threshold below which text is considered low confidence
OCR_CONFIDENCE_THRESHOLD = 0.7