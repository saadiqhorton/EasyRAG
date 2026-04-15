"""File content validation using magic byte signatures.

Validates that uploaded files match their claimed MIME type by checking
file header signatures (magic bytes). This prevents MIME type spoofing
where an attacker sets a benign Content-Type header on a malicious file.
"""

import logging

logger = logging.getLogger(__name__)

# Magic byte signatures for supported file types.
# Each entry maps a MIME type to a list of acceptable byte signatures.
# Signatures are prefix matches from the start of the file.
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [
        b"%PDF",  # PDF files start with %PDF
    ],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",  # DOCX is a ZIP archive (starts with PK signature)
    ],
}

# Text-based formats don't have reliable binary signatures.
# We validate them by checking that the content is valid UTF-8 text.
TEXT_MIME_TYPES: set[str] = {
    "text/markdown",
    "text/x-markdown",
    "text/plain",
    "text/html",
}


def validate_file_signature(content: bytes, claimed_mime: str) -> tuple[bool, str]:
    """Validate that file content matches the claimed MIME type.

    Args:
        content: The raw file bytes (at least first 512 bytes recommended).
        claimed_mime: The MIME type claimed by the upload request.

    Returns:
        Tuple of (is_valid, reason). is_valid is True if the content
        matches the claimed type. reason explains what was detected.
    """
    if not content:
        return False, "File is empty"

    # For text-based formats, verify the content is valid UTF-8
    if claimed_mime in TEXT_MIME_TYPES:
        try:
            content.decode("utf-8")
            return True, "Valid UTF-8 text content"
        except UnicodeDecodeError:
            return False, (
                f"File claimed to be {claimed_mime} but content is not valid UTF-8. "
                f"File may be a binary file with a misleading MIME type."
            )

    # For binary formats with known signatures, check magic bytes
    if claimed_mime in MAGIC_SIGNATURES:
        signatures = MAGIC_SIGNATURES[claimed_mime]
        for sig in signatures:
            if content[:len(sig)] == sig:
                return True, f"Magic byte signature matches {claimed_mime}"

        # Signature didn't match - check if it looks like something else
        detected = _detect_actual_type(content)
        return False, (
            f"File claimed to be {claimed_mime} but signature does not match. "
            f"Actual content appears to be: {detected}"
        )

    # Unknown MIME type - accept without signature validation
    return True, "No signature validation available for this MIME type"


def _detect_actual_type(content: bytes) -> str:
    """Detect the actual file type from content bytes.

    Returns a human-readable description of the detected type.
    """
    if not content:
        return "empty file"

    # Check known signatures
    if content[:4] == b"%PDF":
        return "PDF document"
    if content[:4] == b"PK\x03\x04":
        return "ZIP archive (possibly DOCX/XLSX/PPTX)"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG image"
    if content[:3] == b"\xff\xd8\xff":
        return "JPEG image"
    if content[:4] == b"GIF8":
        return "GIF image"
    if content[:4] == b"RIFF":
        return "RIFF container (possibly AVI/WAV/WebP)"
    if content[:5] == b"<?xml":
        return "XML document"
    if content[:1] == b"{":
        return "JSON data"
    if content[:2] == b"\x1f\x8b":
        return "GZIP archive"

    # Try UTF-8
    try:
        content[:512].decode("utf-8")
        return "text/plain (UTF-8 text)"
    except UnicodeDecodeError:
        pass

    return "unknown binary format"