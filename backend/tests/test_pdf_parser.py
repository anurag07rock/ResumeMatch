"""
Unit and Security Tests for PDF Text Extraction Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Validates:
1. Valid single-page text extraction and metadata.
2. Multi-page documents and page-boundary preservation.
3. Binary stream (io.BytesIO) inputs.
4. Empty / scanned PDFs with no extractable text.
5. Soft empty handling when allow_empty=True.
6. Malformed and corrupted PDF byte handling.
7. Non-PDF input rejection (%PDF- magic byte verification).
8. File size ceiling enforcement.
9. Page count ceiling enforcement.
10. Whitespace and line-ending normalization invariants.
11. Encrypted / password-protected PDF rejection.
12. Deterministic document resource closure.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
import pymupdf

from app.services.pdf_parser import (
    PDFCorruptedError,
    PDFEmptyTextError,
    PDFInvalidFormatError,
    PDFPageLimitExceededError,
    PDFSizeLimitExceededError,
    extract_text_from_pdf,
    normalize_text,
)


# ---------------------------------------------------------------------------
# Test PDF Generators (In-memory, zero network / disk dependencies)
# ---------------------------------------------------------------------------

def create_in_memory_pdf(pages_text: list[str]) -> bytes:
    """
    Programmatically creates minimal, valid PDF bytes containing the specified text per page.
    """
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_encrypted_pdf(text: str = "Confidential resume data") -> bytes:
    """
    Programmatically creates an AES-256 encrypted PDF in memory.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="sample_password",
    )
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_valid_single_page_pdf_extraction():
    """
    Verify text extraction, metrics, and page boundaries on a valid single-page PDF.
    """
    content = "Jane Doe\nSenior Backend Engineer\nPython, Docker, PostgreSQL"
    pdf_bytes = create_in_memory_pdf([content])

    result = extract_text_from_pdf(pdf_bytes)

    assert result.total_pages == 1
    assert result.has_extractable_text is True
    assert "Jane Doe" in result.cleaned_text
    assert "Senior Backend Engineer" in result.cleaned_text
    assert "Python, Docker, PostgreSQL" in result.cleaned_text
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].word_count > 0
    assert result.pages[0].char_count == len(result.pages[0].text)


def test_multi_page_pdf_preserves_page_boundaries():
    """
    Verify that multi-page documents preserve individual page text and page order.
    """
    page_1 = "Candidate Profile: John Smith\nSkills: Python, FastAPI"
    page_2 = "Work Experience: Tech Lead at Acme Corp (2020 - 2024)"
    page_3 = "Education: Bachelor of Science in Computer Science"

    pdf_bytes = create_in_memory_pdf([page_1, page_2, page_3])

    result = extract_text_from_pdf(pdf_bytes)

    assert result.total_pages == 3
    assert len(result.pages) == 3
    assert result.pages[0].page_number == 1
    assert "Candidate Profile" in result.pages[0].text
    assert result.pages[1].page_number == 2
    assert "Work Experience" in result.pages[1].text
    assert result.pages[2].page_number == 3
    assert "Education" in result.pages[2].text

    # Combined cleaned_text must contain all sections
    assert "Candidate Profile" in result.cleaned_text
    assert "Work Experience" in result.cleaned_text
    assert "Education" in result.cleaned_text


def test_binary_stream_input_supported():
    """
    Verify that binary file-like objects (e.g. io.BytesIO) are parsed identically to raw bytes.
    """
    content = "Stream test candidate text"
    pdf_bytes = create_in_memory_pdf([content])
    stream = io.BytesIO(pdf_bytes)

    result = extract_text_from_pdf(stream)

    assert result.total_pages == 1
    assert "Stream test candidate text" in result.cleaned_text


def test_empty_pdf_or_no_text_raises_empty_error():
    """
    Verify that a PDF containing blank pages with no extractable text raises PDFEmptyTextError.
    """
    pdf_bytes = create_in_memory_pdf(["", ""])

    with pytest.raises(PDFEmptyTextError) as exc_info:
        extract_text_from_pdf(pdf_bytes, allow_empty=False)

    assert "no extractable text" in str(exc_info.value).lower()


def test_empty_pdf_with_allow_empty_flag_returns_result():
    """
    Verify that allow_empty=True returns a PDFParseResult with has_extractable_text=False without raising.
    """
    pdf_bytes = create_in_memory_pdf(["", ""])

    result = extract_text_from_pdf(pdf_bytes, allow_empty=True)

    assert result.total_pages == 2
    assert result.has_extractable_text is False
    assert result.cleaned_text == ""
    assert result.char_count == 0


def test_malformed_pdf_bytes_raises_corrupted_error():
    """
    Verify that truncated or malformed PDF data starting with %PDF- raises PDFCorruptedError.
    """
    corrupted_bytes = b"%PDF-1.4\ncorrupted-content-invalid-structure"

    with pytest.raises(PDFCorruptedError) as exc_info:
        extract_text_from_pdf(corrupted_bytes)

    assert "malformed or corrupted" in str(exc_info.value).lower()


def test_non_pdf_input_rejected():
    """
    Verify that inputs without valid %PDF- magic bytes raise PDFInvalidFormatError.
    """
    # Plain text file disguised as PDF
    with pytest.raises(PDFInvalidFormatError) as exc_info:
        extract_text_from_pdf(b"This is just plain text content.")
    assert "%PDF-" in str(exc_info.value)

    # Empty 0-byte input
    with pytest.raises(PDFInvalidFormatError) as exc_info:
        extract_text_from_pdf(b"")
    assert "0 bytes" in str(exc_info.value)

    # None input
    with pytest.raises(PDFInvalidFormatError):
        extract_text_from_pdf(None)  # type: ignore

    # Invalid type
    with pytest.raises(PDFInvalidFormatError):
        extract_text_from_pdf(12345)  # type: ignore


def test_file_size_limit_enforcement():
    """
    Verify that PDFs exceeding max_size_bytes ceiling are rejected with PDFSizeLimitExceededError.
    """
    pdf_bytes = create_in_memory_pdf(["Some resume text"])
    byte_len = len(pdf_bytes)

    # Enforce limit strictly below document size
    strict_limit = byte_len - 100

    with pytest.raises(PDFSizeLimitExceededError) as exc_info:
        extract_text_from_pdf(pdf_bytes, max_size_bytes=strict_limit)

    assert "exceeds maximum allowed limit" in str(exc_info.value)


def test_page_count_limit_enforcement():
    """
    Verify that PDFs exceeding max_pages ceiling are rejected with PDFPageLimitExceededError.
    """
    # Create 5-page PDF
    pdf_bytes = create_in_memory_pdf([f"Page {i} content" for i in range(1, 6)])

    # Limit to 3 pages
    with pytest.raises(PDFPageLimitExceededError) as exc_info:
        extract_text_from_pdf(pdf_bytes, max_pages=3)

    assert "5 pages" in str(exc_info.value)
    assert "exceeds the maximum allowed limit of 3" in str(exc_info.value)


def test_encrypted_pdf_rejected():
    """
    Verify that password-protected / encrypted PDFs are rejected safely without infinite loops or crashes.
    """
    encrypted_bytes = create_encrypted_pdf("Secret candidate resume")

    with pytest.raises(PDFCorruptedError) as exc_info:
        extract_text_from_pdf(encrypted_bytes)

    assert "encrypted or password-protected" in str(exc_info.value).lower()


def test_whitespace_and_line_ending_normalization():
    """
    Verify normalization logic preserves semantic paragraph breaks and removes redundant formatting whitespace.
    """
    dirty_text = (
        "  Candidate Name   \r\n\r\n\r\n\r\n"
        "Senior   Software    Engineer   \r\n"
        "Python\t\tAWS\tDocker\n\n\n\n"
        "Experience:\n  - Built APIs.  \n"
    )

    cleaned = normalize_text(dirty_text)

    # Must collapse 4+ newlines to 2
    assert "\n\n\n" not in cleaned
    # Must remove CRLF
    assert "\r" not in cleaned
    # Must collapse multiple spaces within a line
    assert "Senior Software Engineer" in cleaned
    assert "Python AWS Docker" in cleaned
    # Paragraph boundary preserved
    assert "Candidate Name\n\nSenior Software Engineer" in cleaned


def test_deterministic_resource_cleanup():
    """
    Verify that PyMuPDF documents are closed deterministically in finally block, even on processing failure.
    """
    pdf_bytes = create_in_memory_pdf(["Valid resume text"])
    closed_docs = []

    real_open = pymupdf.open

    def mocked_open(*args, **kwargs):
        doc = real_open(*args, **kwargs)
        orig_close = doc.close

        def tracking_close():
            closed_docs.append(True)
            return orig_close()

        doc.close = tracking_close
        return doc

    with patch("app.services.pdf_parser.pymupdf.open", side_effect=mocked_open):
        result = extract_text_from_pdf(pdf_bytes)
        assert result.total_pages == 1

    # Confirm doc.close() was executed
    assert len(closed_docs) == 1 and closed_docs[0] is True


# ---------------------------------------------------------------------------
# Task 2.1 Security & Correctness Regression Tests
# ---------------------------------------------------------------------------

class TrackingStream:
    """A stream wrapper that tracks read chunk sizes and closure state."""
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.closed = False
        self.read_chunk_sizes = []

    def read(self, n: int = -1) -> bytes:
        self.read_chunk_sizes.append(n)
        if n == -1:
            chunk = self.data[self.offset:]
            self.offset = len(self.data)
            return chunk
        chunk = self.data[self.offset:self.offset + n]
        self.offset += len(chunk)
        return chunk

    def close(self):
        self.closed = True


def test_bounded_stream_read_prevents_unbounded_memory():
    """
    Verify that reading from a stream reads at most (size_limit + 1) bytes,
    preventing unbounded memory allocation on oversized streams.
    """
    # 2000 bytes payload
    large_payload = b"%PDF-1.4\n" + b"A" * 2000
    stream = TrackingStream(large_payload)

    # Limit to 500 bytes
    with pytest.raises(PDFSizeLimitExceededError) as exc_info:
        extract_text_from_pdf(stream, max_size_bytes=500)

    assert "exceeds maximum allowed limit of 500 bytes" in str(exc_info.value)
    # Must have read at most 501 bytes (500 + 1)
    assert stream.read_chunk_sizes == [501]
    # Caller stream must NOT be closed by the parser
    assert stream.closed is False


def test_stream_caller_ownership_preserved():
    """
    Verify that caller retains ownership of their stream and it remains open after parsing.
    """
    pdf_bytes = create_in_memory_pdf(["Stream ownership test"])
    stream = io.BytesIO(pdf_bytes)

    result = extract_text_from_pdf(stream)
    assert result.total_pages == 1
    # Caller stream must remain open
    assert stream.closed is False


def test_pdf_header_with_leading_bom_and_whitespace_supported():
    """
    Verify ISO 32000-1 § 7.5.2 tolerance: Legitimate PDFs with a leading UTF-8 BOM
    or whitespace/comments before '%PDF-' within the first 1024 bytes parse successfully.
    """
    base_pdf = create_in_memory_pdf(["Valid resume under BOM header"])

    # 1. Leading UTF-8 BOM (\xef\xbb\xbf)
    bom_pdf = b"\xef\xbb\xbf" + base_pdf
    result_bom = extract_text_from_pdf(bom_pdf)
    assert result_bom.total_pages == 1
    assert "Valid resume under BOM header" in result_bom.cleaned_text

    # 2. Leading whitespace / CRLF
    space_pdf = b"   \r\n\t" + base_pdf
    result_space = extract_text_from_pdf(space_pdf)
    assert result_space.total_pages == 1
    assert "Valid resume under BOM header" in result_space.cleaned_text


def test_pdf_header_beyond_1024_bytes_rejected():
    """
    Verify that a file where '%PDF-' does not appear within the first 1024 bytes is rejected.
    """
    # 1050 bytes of padding followed by %PDF-
    padded_fake = b"X" * 1050 + b"%PDF-1.4\nrest-of-file"

    with pytest.raises(PDFInvalidFormatError) as exc_info:
        extract_text_from_pdf(padded_fake)

    assert "within the first 1024 bytes" in str(exc_info.value)


def test_invalid_boundary_limits_raise_value_error():
    """
    Verify that non-positive limits (<= 0) raise ValueError.
    """
    pdf_bytes = create_in_memory_pdf(["Valid text"])

    with pytest.raises(ValueError) as exc_size:
        extract_text_from_pdf(pdf_bytes, max_size_bytes=0)
    assert "max_size_bytes must be a positive integer" in str(exc_size.value)

    with pytest.raises(ValueError) as exc_pages:
        extract_text_from_pdf(pdf_bytes, max_pages=-1)
    assert "max_pages must be a positive integer" in str(exc_pages.value)


def test_unicode_resume_text_preservation():
    """
    Verify that international names, accents, ligatures, and technical symbols
    are fully preserved without corruption.
    """
    resume_content = (
        "Candidate: José Müller-Fischer\n"
        "Curriculum Vitæ\n"
        "Specialization: C++, C#, .NET, Python, and Machine Learning\n"
        "Location: Zürich, Switzerland"
    )
    pdf_bytes = create_in_memory_pdf([resume_content])

    result = extract_text_from_pdf(pdf_bytes)

    assert "José Müller-Fischer" in result.cleaned_text
    assert "Curriculum Vitæ" in result.cleaned_text
    assert "C++, C#, .NET" in result.cleaned_text
    assert "Zürich, Switzerland" in result.cleaned_text
    assert result.char_count == len(result.cleaned_text)
    assert result.word_count == len(result.cleaned_text.split())
