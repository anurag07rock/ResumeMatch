"""
Services package initialization.
"""

from app.services.pdf_parser import (
    PDFCorruptedError,
    PDFEmptyTextError,
    PDFInvalidFormatError,
    PDFPage,
    PDFPageLimitExceededError,
    PDFParseResult,
    PDFParserError,
    PDFSizeLimitExceededError,
    extract_text_from_pdf,
    normalize_text,
)
from app.services.taxonomy_service import (
    TaxonomyMetadata,
    TaxonomyService,
    TaxonomySkill,
    taxonomy_service,
)
from app.services.nlp_extractor import (
    ExtractedSkill,
    JobSkillExtractionResult,
    SkillExtractionResult,
    SkillExtractor,
    skill_extractor,
)
from app.services.embedding_service import (
    BatchEmbeddingResult,
    EmbeddingInferenceError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingServiceError,
    ModelLoadError,
    embedding_service,
)

__all__ = [
    # PDF Parser
    "PDFParserError",
    "PDFInvalidFormatError",
    "PDFSizeLimitExceededError",
    "PDFPageLimitExceededError",
    "PDFEmptyTextError",
    "PDFCorruptedError",
    "PDFPage",
    "PDFParseResult",
    "extract_text_from_pdf",
    "normalize_text",
    # Taxonomy Service
    "TaxonomySkill",
    "TaxonomyMetadata",
    "TaxonomyService",
    "taxonomy_service",
    # NLP Extractor
    "ExtractedSkill",
    "SkillExtractionResult",
    "JobSkillExtractionResult",
    "SkillExtractor",
    "skill_extractor",
    # Embedding Service
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "EmbeddingService",
    "embedding_service",
    "EmbeddingServiceError",
    "ModelLoadError",
    "EmbeddingInferenceError",
]

