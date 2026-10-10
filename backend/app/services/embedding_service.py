"""
Vector Embedding Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Provides dense vector embeddings for resume texts and job descriptions using
the `sentence-transformers/all-MiniLM-L6-v2` neural model (384 dimensions).
Adheres strictly to the architectural and engineering governance in AGENTS.md:
- Produces exactly 384-dimensional unit-normalized L2 dense embeddings.
- Sliding-window chunking strategy with mean-pooling aggregation for long documents.
- Controlled lazy singleton loading; zero redundant reloads per request.
- Batch encoding support with vectorized chunk flattening.
- Strict input validation (empty, whitespace, oversized input handling).
- Zero raw text or candidate PII logging.
"""

from __future__ import annotations

import logging
import threading
import unicodedata
from typing import Any, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum document character ceiling (approx 25,000 words / ~50 pages)
MAX_DOCUMENT_CHARS = 150_000


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EmbeddingServiceError(Exception):
    """Base exception for vector embedding operations."""
    pass


class ModelLoadError(EmbeddingServiceError):
    """Raised when the neural embedding model cannot be loaded or initialized."""
    pass


class EmbeddingInferenceError(EmbeddingServiceError):
    """Raised when embedding inference or vector aggregation fails."""
    pass


# ---------------------------------------------------------------------------
# Result Contracts
# ---------------------------------------------------------------------------

class EmbeddingResult(BaseModel):
    """Structured result containing a 384-dimensional unit-normalized embedding."""
    embedding: List[float] = Field(..., description="384-dimensional unit-normalized embedding vector")
    dimensions: int = Field(default=384, description="Vector dimension count (strictly 384)")
    chunk_count: int = Field(default=1, description="Number of sliding-window chunks aggregated")
    model_name: str = Field(..., description="Canonical model identifier")
    normalized: bool = Field(default=True, description="Whether embedding vector is L2 unit normalized")


class BatchEmbeddingResult(BaseModel):
    """Structured result containing multiple document embeddings processed in batch."""
    embeddings: List[List[float]] = Field(..., description="List of 384-dimensional unit-normalized vectors")
    dimensions: int = Field(default=384, description="Vector dimension count (strictly 384)")
    total_documents: int = Field(..., description="Total documents processed in batch")
    model_name: str = Field(..., description="Canonical model identifier")
    chunk_counts: List[int] = Field(default_factory=list, description="Chunk count per document")


# ---------------------------------------------------------------------------
# Embedding Service Implementation
# ---------------------------------------------------------------------------

class EmbeddingService:
    """
    Thread-safe, lazy-loading embedding service wrapping sentence-transformers/all-MiniLM-L6-v2.
    Implements sliding-window chunking with mean pooling for documents exceeding sequence limits.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        expected_dimension: Optional[int] = None,
        max_chunk_size: Optional[int] = None,
        chunk_stride: Optional[int] = None,
        model_instance: Optional[Any] = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.expected_dimension = expected_dimension or settings.EMBEDDING_DIMENSION
        self.max_chunk_size = max_chunk_size or settings.MAX_TOKEN_CHUNK_SIZE
        self.chunk_stride = chunk_stride or settings.CHUNK_STRIDE

        self._model = model_instance
        self._lock = threading.Lock()
        self._load_attempts = 0

    @property
    def is_loaded(self) -> bool:
        """Returns True if the underlying embedding model is loaded in memory."""
        return self._model is not None

    def initialize(self) -> None:
        """
        Idempotently loads the model into memory. Intended for call during application startup
        (e.g., FastAPI lifespan context manager).
        """
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return

            self._load_attempts += 1
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(
                    "Initializing neural embedding model '%s' on CPU",
                    self.model_name,
                )
                self._model = SentenceTransformer(
                    self.model_name,
                    device="cpu",
                )
                logger.info(
                    "Model '%s' successfully loaded (max_seq_length=%d)",
                    self.model_name,
                    getattr(self._model, "max_seq_length", 256),
                )
            except Exception as exc:
                logger.error(
                    "Failed to initialize embedding model '%s': %s",
                    self.model_name,
                    str(exc),
                )
                raise ModelLoadError(
                    f"Could not load embedding model '{self.model_name}': {exc}"
                ) from exc

    def _ensure_model(self) -> Any:
        """Ensures the model is loaded before performing inference."""
        if self._model is None:
            self.initialize()
        return self._model

    @staticmethod
    def _validate_and_normalize_text(text: str) -> str:
        """
        Validates input boundaries and normalizes whitespace without logging content.
        Raises ValueError for empty, whitespace-only, or oversized inputs.
        """
        if not isinstance(text, str):
            raise TypeError(f"Expected text input of type str, got {type(text).__name__}")

        if not text or not text.strip():
            raise ValueError("Input text cannot be empty or whitespace-only.")

        if len(text) > MAX_DOCUMENT_CHARS:
            raise ValueError(
                f"Input text exceeds maximum allowed size of {MAX_DOCUMENT_CHARS} characters "
                f"(received {len(text)} characters)."
            )

        # Unicode normalization (NFKC) and newline normalization
        cleaned = unicodedata.normalize("NFKC", text)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n").strip()
        return cleaned

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits text into deterministic sliding-window chunks if sequence length exceeds
        the model's token limits.
        Leaves exact headroom for model special tokens (e.g. [CLS], [SEP]) so boundary
        tokens are never silently discarded through model-side truncation.
        """
        cleaned = self._validate_and_normalize_text(text)
        model = self._ensure_model()

        # Determine effective context ceiling from model and configuration
        model_limit = getattr(model, "max_seq_length", 256)
        effective_chunk_size = min(self.max_chunk_size, model_limit)

        tokenizer = getattr(model, "tokenizer", None)
        num_special = 2
        if tokenizer is not None and hasattr(tokenizer, "num_special_tokens_to_add"):
            try:
                num_special = tokenizer.num_special_tokens_to_add(pair=False)
            except Exception:
                num_special = 2

        # Reserve exact space for special tokens added during model encoding
        max_payload_tokens = max(1, effective_chunk_size - num_special)
        effective_stride = min(self.chunk_stride, max_payload_tokens)
        if effective_stride <= 0:
            effective_stride = max_payload_tokens

        if tokenizer is not None and hasattr(tokenizer, "encode") and hasattr(tokenizer, "decode"):
            # Tokenizer-based token slicing
            try:
                token_ids = tokenizer.encode(cleaned, add_special_tokens=False)
            except Exception:
                token_ids = []

            if len(token_ids) <= max_payload_tokens:
                return [cleaned]

            chunks: List[str] = []
            for i in range(0, len(token_ids), effective_stride):
                chunk_ids = token_ids[i : i + max_payload_tokens]
                chunk_str = tokenizer.decode(chunk_ids, skip_special_tokens=True).strip()
                if chunk_str:
                    # Guard decode/re-tokenize boundary inflation: ensure re-tokenized string
                    # does not exceed max_payload_tokens when SentenceTransformer encodes it
                    try:
                        re_tokens = tokenizer.encode(chunk_str, add_special_tokens=False)
                        while len(re_tokens) > max_payload_tokens and len(chunk_ids) > 1:
                            excess = len(re_tokens) - max_payload_tokens
                            chunk_ids = chunk_ids[:-excess]
                            chunk_str = tokenizer.decode(chunk_ids, skip_special_tokens=True).strip()
                            re_tokens = tokenizer.encode(chunk_str, add_special_tokens=False)
                    except Exception:
                        pass
                    if chunk_str:
                        chunks.append(chunk_str)
                if i + max_payload_tokens >= len(token_ids):
                    break

            return chunks if chunks else [cleaned]

        # Word-level fallback chunking (when using mocked models without HuggingFace tokenizer)
        words = cleaned.split()
        if len(words) <= max_payload_tokens:
            return [cleaned]

        chunks = []
        for i in range(0, len(words), effective_stride):
            chunk_words = words[i : i + max_payload_tokens]
            chunks.append(" ".join(chunk_words))
            if i + max_payload_tokens >= len(words):
                break

        return chunks if chunks else [cleaned]

    @staticmethod
    def _aggregate_chunk_embeddings(chunk_embeddings: np.ndarray) -> np.ndarray:
        """
        Combines multiple chunk embeddings into a single document vector via mean pooling,
        followed by L2 unit normalization.
        """
        if len(chunk_embeddings) == 1:
            vec = chunk_embeddings[0]
        else:
            # Mean pooling across chunk vectors
            vec = np.mean(chunk_embeddings, axis=0)

        # L2 unit normalization
        norm = np.linalg.norm(vec)
        if norm == 0 or not np.isfinite(norm):
            raise EmbeddingInferenceError("Calculated embedding has invalid zero or non-finite norm.")

        unit_vec = vec / norm
        return unit_vec

    def embed_text(self, text: str) -> EmbeddingResult:
        """
        Generates a 384-dimensional unit-normalized embedding for a single text document.
        Handles sliding-window chunking and mean pooling transparently.
        """
        cleaned = self._validate_and_normalize_text(text)
        chunks = self.chunk_text(cleaned)
        model = self._ensure_model()

        try:
            # Encode chunks with SentenceTransformer
            raw_embeddings = model.encode(
                chunks,
                batch_size=len(chunks),
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except Exception as exc:
            logger.error("Embedding inference error: %s", str(exc))
            raise EmbeddingInferenceError(f"Embedding inference failed: {exc}") from exc

        # Ensure 2D numpy array
        if isinstance(raw_embeddings, list):
            raw_embeddings = np.array(raw_embeddings)
        elif raw_embeddings.ndim == 1:
            raw_embeddings = raw_embeddings.reshape(1, -1)

        aggregated = self._aggregate_chunk_embeddings(raw_embeddings)

        # Dimensionality and finiteness assertions
        if aggregated.shape[0] != self.expected_dimension:
            raise EmbeddingInferenceError(
                f"Embedding dimension mismatch: expected {self.expected_dimension}, got {aggregated.shape[0]}"
            )

        if not np.all(np.isfinite(aggregated)):
            raise EmbeddingInferenceError("Embedding vector contains non-finite values (NaN or Inf).")

        return EmbeddingResult(
            embedding=aggregated.tolist(),
            dimensions=self.expected_dimension,
            chunk_count=len(chunks),
            model_name=self.model_name,
            normalized=True,
        )

    def embed_batch(
        self, texts: List[str], batch_size: int = 32
    ) -> BatchEmbeddingResult:
        """
        Encodes a list of text documents in batch mode with vectorized chunk flattening.
        Returns a BatchEmbeddingResult containing unit-normalized 384-d vectors.
        """
        if not isinstance(texts, list):
            raise TypeError(f"Expected texts input of type list, got {type(texts).__name__}")

        if not texts:
            return BatchEmbeddingResult(
                embeddings=[],
                dimensions=self.expected_dimension,
                total_documents=0,
                model_name=self.model_name,
                chunk_counts=[],
            )

        # Validate and chunk each document
        all_chunks: List[str] = []
        doc_slices: List[Tuple[int, int]] = []
        chunk_counts: List[int] = []

        idx = 0
        for doc_text in texts:
            chunks = self.chunk_text(doc_text)
            n_chunks = len(chunks)
            all_chunks.extend(chunks)
            doc_slices.append((idx, idx + n_chunks))
            chunk_counts.append(n_chunks)
            idx += n_chunks

        model = self._ensure_model()

        try:
            raw_embeddings = model.encode(
                all_chunks,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except Exception as exc:
            logger.error("Batch embedding inference error: %s", str(exc))
            raise EmbeddingInferenceError(f"Batch embedding inference failed: {exc}") from exc

        if isinstance(raw_embeddings, list):
            raw_embeddings = np.array(raw_embeddings)
        elif raw_embeddings.ndim == 1:
            raw_embeddings = raw_embeddings.reshape(1, -1)

        doc_embeddings: List[List[float]] = []
        for start, end in doc_slices:
            slice_embs = raw_embeddings[start:end]
            aggregated = self._aggregate_chunk_embeddings(slice_embs)

            if aggregated.shape[0] != self.expected_dimension:
                raise EmbeddingInferenceError(
                    f"Dimension mismatch in batch: expected {self.expected_dimension}, got {aggregated.shape[0]}"
                )
            if not np.all(np.isfinite(aggregated)):
                raise EmbeddingInferenceError("Non-finite values detected in batch embedding.")

            doc_embeddings.append(aggregated.tolist())

        return BatchEmbeddingResult(
            embeddings=doc_embeddings,
            dimensions=self.expected_dimension,
            total_documents=len(texts),
            model_name=self.model_name,
            chunk_counts=chunk_counts,
        )

    def generate_embedding(self, text: str) -> List[float]:
        """
        Convenience method returning the raw 384-dimensional float list embedding directly.
        """
        return self.embed_text(text).embedding


# Default module-level singleton instance
embedding_service = EmbeddingService()
