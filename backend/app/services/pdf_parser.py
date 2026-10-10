"""
PDF Text Extraction Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Provides robust, sandboxed PDF text extraction using PyMuPDF (pymupdf).
Adheres strictly to the security, privacy, and architectural guidelines defined in
docs/SECURITY.md and docs/PRODUCT_REQUIREMENTS.md:
- Enforces strict file-size and page-count ceilings (5 MB / 10 pages).
- Validates %PDF- magic bytes to reject disguised payloads.
- Layout-aware block-level extraction preserving reading order and page boundaries.
- Deterministic in-memory resource cleanup without writing to disk.
- Zero external network dependencies, OCR fabrication, or PII leakage.
"""

from __future__ import annotations

import io
import re
from typing import BinaryIO, List

import pymupdf
from pydantic import BaseModel, Field

from app.core.config import settings


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class PDFParserError(Exception):
    """Base exception for all PDF parsing and ingestion errors."""
    pass


class PDFInvalidFormatError(PDFParserError):
    """Raised when the input is not a valid PDF or is missing '%PDF-' magic bytes."""
    pass


class PDFSizeLimitExceededError(PDFParserError):
    """Raised when the PDF file size exceeds the configured maximum byte limit."""
    pass


class PDFPageLimitExceededError(PDFParserError):
    """Raised when the PDF page count exceeds the configured maximum page limit."""
    pass


class PDFEmptyTextError(PDFParserError):
    """Raised when the PDF contains no extractable text (blank or scanned/image-only)."""
    pass


class PDFCorruptedError(PDFParserError):
    """Raised when the PDF document is corrupted, malformed, or encrypted."""
    pass


# ---------------------------------------------------------------------------
# Structured Models
# ---------------------------------------------------------------------------

class PDFPage(BaseModel):
    """
    Extracted text and structural metrics for an individual PDF page.
    """
    page_number: int = Field(..., description="1-indexed page number within the document")
    text: str = Field(..., description="Normalized text extracted from this page")
    char_count: int = Field(..., description="Total character count on this page")
    word_count: int = Field(..., description="Total word count on this page")


class PDFParseResult(BaseModel):
    """
    Complete result envelope of a parsed PDF document.
    """
    total_pages: int = Field(..., description="Total number of pages processed")
    raw_text: str = Field(..., description="Raw text concatenated across all pages")
    cleaned_text: str = Field(..., description="Normalized, whitespace-cleaned concatenated text")
    char_count: int = Field(..., description="Total character count in cleaned text")
    word_count: int = Field(..., description="Total word count in cleaned text")
    pages: List[PDFPage] = Field(default_factory=list, description="Per-page extracted text records")
    has_extractable_text: bool = Field(..., description="True if document contains readable text")


# ---------------------------------------------------------------------------
# Text Normalization Utilities
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalizes extracted text:
    - Standardizes CRLF and CR line endings to LF.
    - Strips NULL bytes and control characters (preserving tab and newline).
    - Removes trailing whitespace per line.
    - Replaces runs of multiple horizontal spaces/tabs with a single space.
    - Collapses 3 or more consecutive newlines into 2 (paragraph break).
    """
    if not text:
        return ""

    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip null bytes and non-printable control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Clean line by line: collapse horizontal whitespace, strip edges
    cleaned_lines: List[str] = []
    for line in text.split("\n"):
        # Collapse multiple horizontal whitespace characters to a single space
        line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # 4. Collapse runs of 3+ consecutive newlines down to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------

def extract_text_from_pdf(
    pdf_input: bytes | bytearray | BinaryIO,
    max_size_bytes: int | None = None,
    max_pages: int | None = None,
    allow_empty: bool = False,
) -> PDFParseResult:
    """
    Extracts text and page-boundary metadata from a PDF document in memory.

    Parameters:
    - pdf_input: Raw PDF bytes, bytearray, or binary file-like stream (e.g. io.BytesIO).
    - max_size_bytes: Maximum allowed file size in bytes (defaults to settings.MAX_PDF_SIZE_BYTES, 5 MB).
    - max_pages: Maximum allowed page count (defaults to settings.MAX_PDF_PAGES, 10 pages).
    - allow_empty: If False (default), raises PDFEmptyTextError when no extractable text is found.
                   If True, returns a PDFParseResult with has_extractable_text=False.

    Returns:
    - PDFParseResult containing total pages, cleaned text, per-page breakdown, and metrics.

    Raises:
    - PDFInvalidFormatError: If input is None, invalid type, empty (0 bytes), or lacks '%PDF-' magic bytes.
    - PDFSizeLimitExceededError: If byte size exceeds max_size_bytes.
    - PDFPageLimitExceededError: If page count exceeds max_pages.
    - PDFEmptyTextError: If no extractable text exists and allow_empty is False.
    - PDFCorruptedError: If the document is corrupted, malformed, or encrypted.
    """
    size_limit = max_size_bytes if max_size_bytes is not None else settings.MAX_PDF_SIZE_BYTES
    page_limit = max_pages if max_pages is not None else settings.MAX_PDF_PAGES

    # 1. Validate parameter limits
    if size_limit <= 0:
        raise ValueError(f"max_size_bytes must be a positive integer, got {size_limit}.")
    if page_limit <= 0:
        raise ValueError(f"max_pages must be a positive integer, got {page_limit}.")

    # 2. Validate input type and convert to bytes with bounded memory consumption
    if pdf_input is None:
        raise PDFInvalidFormatError("PDF input cannot be None.")

    if isinstance(pdf_input, (bytes, bytearray)):
        if len(pdf_input) > size_limit:
            raise PDFSizeLimitExceededError(
                f"PDF file size ({len(pdf_input)} bytes) exceeds maximum allowed limit of {size_limit} bytes."
            )
        pdf_bytes = bytes(pdf_input)
    elif hasattr(pdf_input, "read") and callable(pdf_input.read):
        try:
            # Bounded stream read: read at most (size_limit + 1) bytes to detect oversize
            # streams without exhausting memory. The caller retains ownership of the stream.
            chunk = pdf_input.read(size_limit + 1)
            if not isinstance(chunk, (bytes, bytearray)):
                raise PDFInvalidFormatError("Stream read did not return binary data.")
            if len(chunk) > size_limit:
                raise PDFSizeLimitExceededError(
                    f"PDF stream size exceeds maximum allowed limit of {size_limit} bytes."
                )
            pdf_bytes = bytes(chunk)
        except Exception as exc:
            if isinstance(exc, PDFParserError):
                raise
            raise PDFInvalidFormatError("Failed to read binary data from stream.") from exc
    else:
        raise PDFInvalidFormatError(
            f"Unsupported input type '{type(pdf_input).__name__}'. Expected bytes, bytearray, or binary stream."
        )

    # 3. Check for empty input (0 bytes)
    byte_length = len(pdf_bytes)
    if byte_length == 0:
        raise PDFInvalidFormatError("PDF document is empty (0 bytes).")

    # 4. Header Verification per ISO 32000-1 § 7.5.2
    # The header '%PDF-' must appear within the first 1024 bytes of the file.
    # Note: Header inspection verifies declared container format (rejecting plain text,
    # images, and executables), but does not guarantee immunity against malicious polyglots;
    # deeper parsing sandboxing is enforced by PyMuPDF with script execution disabled.
    header_offset = pdf_bytes[:1024].find(b"%PDF-")
    if header_offset == -1:
        raise PDFInvalidFormatError(
            "File does not contain valid PDF magic header '%PDF-' within the first 1024 bytes."
        )

    # 5. In-Memory PyMuPDF Parsing with Deterministic Cleanup
    doc: pymupdf.Document | None = None
    try:
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise PDFCorruptedError("PDF document is malformed or corrupted and cannot be parsed.") from exc

        # 5. Security Inspection: Check encryption
        if doc.is_encrypted:
            raise PDFCorruptedError("PDF document is encrypted or password-protected and cannot be parsed.")

        total_pages = doc.page_count

        # 6. Page limit check
        if total_pages > page_limit:
            raise PDFPageLimitExceededError(
                f"PDF contains {total_pages} pages, which exceeds the maximum allowed limit of {page_limit} pages."
            )

        if total_pages == 0:
            if not allow_empty:
                raise PDFEmptyTextError("PDF contains 0 pages and has no extractable content.")
            return PDFParseResult(
                total_pages=0,
                raw_text="",
                cleaned_text="",
                char_count=0,
                word_count=0,
                pages=[],
                has_extractable_text=False,
            )

        # 7. Page-by-page layout-aware text extraction
        pages_result: List[PDFPage] = []
        raw_page_texts: List[str] = []
        cleaned_page_texts: List[str] = []

        for page_idx in range(total_pages):
            page = doc[page_idx]

            # Extract layout text blocks: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type == 0 indicates text; block_type == 1 indicates image
            blocks = page.get_text("blocks")
            text_blocks = [b for b in blocks if len(b) >= 7 and b[6] == 0]

            if text_blocks:
                # Sort blocks top-to-bottom (y0), then left-to-right (x0) for natural reading order
                sorted_blocks = sorted(text_blocks, key=lambda b: (b[1], b[0]))
                page_raw = "\n".join(b[4].strip() for b in sorted_blocks if b[4].strip())
            else:
                # Fallback to standard plain text extraction if no structured text blocks
                page_raw = page.get_text("text").strip()

            page_cleaned = normalize_text(page_raw)
            char_count = len(page_cleaned)
            word_count = len(page_cleaned.split()) if page_cleaned else 0

            pages_result.append(
                PDFPage(
                    page_number=page_idx + 1,
                    text=page_cleaned,
                    char_count=char_count,
                    word_count=word_count,
                )
            )
            raw_page_texts.append(page_raw)
            cleaned_page_texts.append(page_cleaned)

        raw_full_text = "\n\n".join(raw_page_texts).strip()
        cleaned_full_text = "\n\n".join(t for t in cleaned_page_texts if t).strip()

        has_extractable_text = bool(cleaned_full_text and len(cleaned_full_text) > 0)

        # 8. Empty / Scanned PDF check
        if not has_extractable_text and not allow_empty:
            raise PDFEmptyTextError(
                "PDF contains no extractable text. Scanned or image-only documents without a text layer are not supported."
            )

        return PDFParseResult(
            total_pages=total_pages,
            raw_text=raw_full_text,
            cleaned_text=cleaned_full_text,
            char_count=len(cleaned_full_text),
            word_count=len(cleaned_full_text.split()) if cleaned_full_text else 0,
            pages=pages_result,
            has_extractable_text=has_extractable_text,
        )

    finally:
        # Deterministic resource closure
        if doc is not None and not doc.is_closed:
            doc.close()
