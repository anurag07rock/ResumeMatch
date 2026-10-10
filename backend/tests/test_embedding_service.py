"""
Unit Tests for Vector Embedding Service
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform

Validates:
1. 384-dimensional output shape.
2. Finite numeric values and unit L2 normalization (norm == 1.0).
3. Rejection of empty, whitespace-only, and oversized inputs.
4. Deterministic output reproducibility for fixed inputs.
5. Sliding-window chunking and overlap for documents exceeding sequence limits.
6. Mean-pooling aggregation across multiple chunks.
7. Vectorized batch encoding and chunk reconstruction.
8. Controlled error handling for model load failure and inference failure.
9. Lazy singleton lifecycle and idempotent initialization.
10. Hermetic offline execution via controlled mock fixtures.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.services.embedding_service import (
    BatchEmbeddingResult,
    EmbeddingInferenceError,
    EmbeddingResult,
    EmbeddingService,
    MAX_DOCUMENT_CHARS,
    ModelLoadError,
)


# ---------------------------------------------------------------------------
# Test Fixtures (Controlled Hermetic Mock Model)
# ---------------------------------------------------------------------------

class FakeTokenizer:
    """Deterministic mock tokenizer simulating word-piece encoding and decoding."""

    def __init__(self, vocab_size: int = 100000):
        self.vocab_size = vocab_size
        self._word_to_id = {}
        self._id_to_word = {}

    def num_special_tokens_to_add(self, pair: bool = False) -> int:
        return 2

    def encode(self, text: str, add_special_tokens: bool = False):
        # Deterministic pseudo tokenization: split into words, map to unique ints
        words = text.split()
        ids = []
        for w in words:
            if w not in self._word_to_id:
                tid = len(self._word_to_id) + 1
                self._word_to_id[w] = tid
                self._id_to_word[tid] = w
            else:
                tid = self._word_to_id[w]
            ids.append(tid)
        return ids

    def decode(self, token_ids, skip_special_tokens: bool = True):
        # Decode back to source word strings
        return " ".join([self._id_to_word.get(tid, f"tok_{tid}") for tid in token_ids])


class FakeSentenceTransformer:
    """Deterministic mock SentenceTransformer returning unit-normalized 384-d vectors."""

    def __init__(self, dimension: int = 384, max_seq_length: int = 256):
        self.dimension = dimension
        self.max_seq_length = max_seq_length
        self.tokenizer = FakeTokenizer()
        self.encode_call_count = 0

    def encode(
        self,
        sentences,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ):
        self.encode_call_count += 1
        if isinstance(sentences, str):
            input_list = [sentences]
        else:
            input_list = list(sentences)

        embeddings = []
        for text in input_list:
            # Deterministic vector based on text content hash
            seed = abs(hash(text)) % (2**32)
            rng = np.random.RandomState(seed)
            raw = rng.randn(self.dimension).astype(np.float32)
            if normalize_embeddings:
                norm = np.linalg.norm(raw)
                raw = raw / (norm if norm > 0 else 1.0)
            embeddings.append(raw)

        return np.array(embeddings, dtype=np.float32)


@pytest.fixture
def mock_model():
    """Provides a fresh fake SentenceTransformer with 384 dimensions and 256 context."""
    return FakeSentenceTransformer(dimension=384, max_seq_length=256)


@pytest.fixture
def service_with_mock(mock_model):
    """Provides an EmbeddingService pre-configured with the mock model."""
    return EmbeddingService(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        expected_dimension=384,
        max_chunk_size=256,
        chunk_stride=128,
        model_instance=mock_model,
    )


# ---------------------------------------------------------------------------
# 1. Output Dimensionality & Normalization
# ---------------------------------------------------------------------------

def test_embedding_output_shape_and_type(service_with_mock):
    """Verify output contains exactly 384 finite float dimensions."""
    sample_text = "Senior Python engineer with experience in distributed backend architecture."
    result = service_with_mock.embed_text(sample_text)

    assert isinstance(result, EmbeddingResult)
    assert result.dimensions == 384
    assert len(result.embedding) == 384
    assert result.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert result.chunk_count == 1
    assert result.normalized is True


def test_finite_numeric_values_and_unit_norm(service_with_mock):
    """Verify that all vector values are finite and the L2 norm equals 1.0."""
    sample_text = "Proficient in PostgreSQL, Redis, Docker, and Kubernetes."
    result = service_with_mock.embed_text(sample_text)

    vec = np.array(result.embedding)
    assert np.all(np.isfinite(vec)), "Vector must not contain NaN or Inf values"

    norm = np.linalg.norm(vec)
    assert np.isclose(norm, 1.0, atol=1e-5), f"Expected unit norm 1.0, got {norm}"


# ---------------------------------------------------------------------------
# 2. Input Boundary Validation
# ---------------------------------------------------------------------------

def test_empty_and_whitespace_inputs_rejected(service_with_mock):
    """Verify that empty, whitespace-only, and non-string inputs raise ValueError/TypeError."""
    # Empty string
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        service_with_mock.embed_text("")

    # Whitespace only
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        service_with_mock.embed_text("   \n\t   ")

    # Non-string input
    with pytest.raises(TypeError, match="Expected text input of type str"):
        service_with_mock.embed_text(12345)  # type: ignore


def test_oversized_input_rejected(service_with_mock):
    """Verify that inputs exceeding MAX_DOCUMENT_CHARS raise a descriptive ValueError."""
    oversized_text = "word " * (MAX_DOCUMENT_CHARS // 4 + 100)
    assert len(oversized_text) > MAX_DOCUMENT_CHARS

    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        service_with_mock.embed_text(oversized_text)


# ---------------------------------------------------------------------------
# 3. Determinism & Convenience Methods
# ---------------------------------------------------------------------------

def test_deterministic_reproducibility(service_with_mock):
    """Verify that identical inputs produce 100% bit-exact embedding vectors."""
    text = "Full-stack developer with React, TypeScript, Node.js, and PostgreSQL expertise."
    result_1 = service_with_mock.embed_text(text)
    result_2 = service_with_mock.embed_text(text)

    assert result_1.embedding == result_2.embedding
    assert np.array_equal(np.array(result_1.embedding), np.array(result_2.embedding))


def test_generate_embedding_convenience_method(service_with_mock):
    """Verify that generate_embedding returns a list of floats directly."""
    text = "Staff Engineer specializing in cloud infrastructure."
    raw_vec = service_with_mock.generate_embedding(text)

    assert isinstance(raw_vec, list)
    assert len(raw_vec) == 384
    assert all(isinstance(v, float) for v in raw_vec)


# ---------------------------------------------------------------------------
# 4. Long-Text Chunking & Mean-Pooling Aggregation
# ---------------------------------------------------------------------------

def test_long_document_sliding_window_chunking(service_with_mock):
    """Verify that documents exceeding the sequence limit are partitioned into overlapping chunks."""
    # Create text with 400 words (exceeds max_chunk_size=256)
    long_text = " ".join([f"term_{i}" for i in range(400)])
    chunks = service_with_mock.chunk_text(long_text)

    # With 400 tokens, chunk_size=256, stride=128:
    # Chunk 0: [0:256] (256 tokens)
    # Chunk 1: [128:384] (256 tokens)
    # Chunk 2: [256:400] (144 tokens)
    assert len(chunks) == 3
    assert all(isinstance(c, str) and len(c) > 0 for c in chunks)


def test_multi_chunk_embedding_aggregation(service_with_mock):
    """Verify that multiple chunks are mean-pooled and re-normalized to unit length."""
    long_text = " ".join([f"keyword_{i}" for i in range(400)])
    result = service_with_mock.embed_text(long_text)

    assert result.chunk_count == 3
    assert result.dimensions == 384
    vec = np.array(result.embedding)
    assert np.all(np.isfinite(vec))
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-5)


def test_short_document_uses_single_chunk(service_with_mock):
    """Verify short documents produce exactly 1 chunk."""
    short_text = "Short job description for a frontend engineer."
    chunks = service_with_mock.chunk_text(short_text)
    assert len(chunks) == 1

    result = service_with_mock.embed_text(short_text)
    assert result.chunk_count == 1


# ---------------------------------------------------------------------------
# 5. Batch Processing
# ---------------------------------------------------------------------------

def test_embed_batch_mixed_document_lengths(service_with_mock):
    """Verify batch encoding handles short and long documents correctly."""
    doc_1 = "Senior backend engineer with Go and AWS."
    doc_2 = " ".join([f"experience_{i}" for i in range(400)])  # 3 chunks
    doc_3 = "Data engineer with PySpark, Snowflake, and dbt."

    batch_result = service_with_mock.embed_batch([doc_1, doc_2, doc_3], batch_size=4)

    assert isinstance(batch_result, BatchEmbeddingResult)
    assert batch_result.total_documents == 3
    assert len(batch_result.embeddings) == 3
    assert batch_result.chunk_counts == [1, 3, 1]

    # Verify each vector is 384-d and unit normalized
    for idx, emb in enumerate(batch_result.embeddings):
        assert len(emb) == 384
        vec = np.array(emb)
        assert np.all(np.isfinite(vec))
        assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-5)

    # Consistency with single document embed_text
    single_res_1 = service_with_mock.embed_text(doc_1)
    assert np.isclose(
        np.dot(batch_result.embeddings[0], single_res_1.embedding), 1.0, atol=1e-4
    )


def test_embed_batch_empty_list(service_with_mock):
    """Verify empty input list returns an empty BatchEmbeddingResult gracefully."""
    empty_batch = service_with_mock.embed_batch([])
    assert empty_batch.total_documents == 0
    assert empty_batch.embeddings == []
    assert empty_batch.chunk_counts == []


# ---------------------------------------------------------------------------
# 6. Error Handling & Lifecycle Idempotency
# ---------------------------------------------------------------------------

def test_model_load_failure_raises_model_load_error():
    """Verify that failure during model loading raises ModelLoadError."""
    service = EmbeddingService(model_name="non-existent/model-path")

    with patch(
        "sentence_transformers.SentenceTransformer",
        side_effect=RuntimeError("Network unreachable / model not found"),
    ):
        with pytest.raises(ModelLoadError, match="Could not load embedding model"):
            service.initialize()


def test_inference_failure_raises_embedding_inference_error(service_with_mock):
    """Verify that failure during forward pass raises EmbeddingInferenceError."""
    # Force encode to raise an exception
    service_with_mock._model.encode = MagicMock(side_effect=RuntimeError("CUDA Out of Memory"))

    with pytest.raises(EmbeddingInferenceError, match="Embedding inference failed"):
        service_with_mock.embed_text("Sample input text")


def test_lifecycle_lazy_loading_and_idempotency():
    """Verify model is not loaded until initialize() or embed_text() is called, and is idempotent."""
    mock_st_class = MagicMock(return_value=FakeSentenceTransformer())

    with patch("sentence_transformers.SentenceTransformer", mock_st_class):
        service = EmbeddingService(model_name="test-model")
        # 1. Not loaded on construction
        assert service.is_loaded is False
        assert mock_st_class.call_count == 0

        # 2. First initialize loads model
        service.initialize()
        assert service.is_loaded is True
        assert mock_st_class.call_count == 1

        # 3. Second initialize is idempotent (no-op)
        service.initialize()
        assert mock_st_class.call_count == 1


# ---------------------------------------------------------------------------
# 7. Real Model Inference Smoke Test (Locally Cached all-MiniLM-L6-v2)
# ---------------------------------------------------------------------------

def test_live_model_inference_smoke_test():
    """
    Smoke test running real inference with all-MiniLM-L6-v2 against the locally cached weights.
    Verifies real SentenceTransformer execution, exact 384-dimensional output, and unit normalization.
    """
    real_service = EmbeddingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
    real_service.initialize()
    assert real_service.is_loaded is True

    sample_doc = (
        "Senior Backend Engineer with 5+ years building scalable microservices in Python and FastAPI. "
        "Experienced in PostgreSQL database optimization, Redis caching, and Docker containerization."
    )
    result = real_service.embed_text(sample_doc)

    assert isinstance(result, EmbeddingResult)
    assert result.dimensions == 384
    assert len(result.embedding) == 384
    assert result.chunk_count == 1
    assert result.model_name == "sentence-transformers/all-MiniLM-L6-v2"

    vec = np.array(result.embedding)
    assert np.all(np.isfinite(vec)), "Vector must contain finite numeric values"
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-5), "Vector must be strictly unit L2 normalized"


# ---------------------------------------------------------------------------
# 8. Task 4.1 Regression Tests: Boundary Headroom, Overlap & Batch Consistency
# ---------------------------------------------------------------------------

def test_boundary_chunk_special_tokens_headroom():
    """
    Verify that the chunking calculation dynamically reserves headroom for special
    tokens ([CLS] and [SEP]) so boundary tokens are never truncated model-side.
    """
    real_service = EmbeddingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
    real_service.initialize()
    tokenizer = real_service._model.tokenizer
    max_seq_length = real_service._model.max_seq_length

    # Test both simple words and complex subword tokens with punctuation
    texts_to_test = [
        " ".join([f"word_{i}" for i in range(500)]),
        " ".join(["technologies", "PostgreSQL", "microservices", "kubernetes", "cloud-native", "CI/CD", "asynchronously", "hyperparameter", "multi-threading", "1234567890"] * 50),
    ]

    for boundary_text in texts_to_test:
        chunks = real_service.chunk_text(boundary_text)
        assert len(chunks) > 1

        for idx, chunk in enumerate(chunks):
            encoded = tokenizer(chunk, truncation=True, max_length=max_seq_length)
            input_ids = encoded["input_ids"]

            # 1. Total tokens with [CLS] and [SEP] must never exceed model capacity
            assert len(input_ids) <= max_seq_length, f"Chunk {idx} exceeded max_seq_length!"

            # 2. First token is [CLS] and last token is [SEP]
            assert input_ids[0] == tokenizer.cls_token_id
            assert input_ids[-1] == tokenizer.sep_token_id

            # 3. Payload tokens inside input_ids must not have been truncated
            untruncated_encoded = tokenizer(chunk, truncation=False)
            assert len(untruncated_encoded["input_ids"]) == len(input_ids), (
                f"Chunk {idx} suffered silent truncation! "
                f"Expected {len(untruncated_encoded['input_ids'])}, got {len(input_ids)}"
            )


def test_stride_and_overlap_invariants(service_with_mock):
    """
    Verify adjacent chunks overlap as intended, and no source token is skipped
    from start to finish.
    """
    # 400 words
    source_words = [f"token_{i}" for i in range(400)]
    source_text = " ".join(source_words)
    chunks = service_with_mock.chunk_text(source_text)

    # Decode chunk words
    chunk_word_lists = [c.split() for c in chunks]

    # 1. Verify every chunk has non-empty words
    assert all(len(cw) > 0 for cw in chunk_word_lists)

    # 2. Verify adjacent chunks overlap by checking that the start of chunk[i+1]
    # appears before the end of chunk[i]
    for i in range(len(chunk_word_lists) - 1):
        c_curr = set(chunk_word_lists[i])
        c_next = set(chunk_word_lists[i + 1])
        overlap = c_curr.intersection(c_next)
        assert len(overlap) > 0, f"Chunk {i} and {i+1} have zero overlap!"

    # 3. Verify every source token appears in at least one chunk (no skipped tokens)
    all_chunk_words = {w for cw in chunk_word_lists for w in cw}
    for word in source_words:
        assert word in all_chunk_words, f"Source token '{word}' was skipped in chunking!"


def test_every_chunk_contributes_to_final_embedding(service_with_mock):
    """
    Verify that every chunk contributes to the multi-chunk mean-pooled embedding.
    Modifying any individual chunk changes the resulting aggregate vector.
    """
    words_a = [f"word_{i}" for i in range(400)]
    # Create words_b where only the last chunk (tokens 350-399) is modified
    words_b = list(words_a)
    for i in range(350, 400):
        words_b[i] = f"modified_tail_{i}"

    text_a = " ".join(words_a)
    text_b = " ".join(words_b)

    res_a = service_with_mock.embed_text(text_a)
    res_b = service_with_mock.embed_text(text_b)

    assert res_a.chunk_count == res_b.chunk_count == 3
    # Vectors must be different because tail chunk changed
    assert not np.allclose(res_a.embedding, res_b.embedding, atol=1e-3)


def test_batch_validation_consistency(service_with_mock):
    """
    Verify input validation in embed_batch is consistent with single-text validation,
    and preserves input order.
    """
    # 1. Non-list input raises TypeError
    with pytest.raises(TypeError, match="Expected texts input of type list"):
        service_with_mock.embed_batch("not a list")  # type: ignore

    # 2. List containing empty text raises ValueError
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        service_with_mock.embed_batch(["Valid text", "", "Another valid text"])

    # 3. List containing whitespace-only text raises ValueError
    with pytest.raises(ValueError, match="cannot be empty or whitespace-only"):
        service_with_mock.embed_batch(["Valid text", "   \t\n  "])

    # 4. List containing oversized text raises ValueError
    oversized = "x " * (MAX_DOCUMENT_CHARS // 2 + 10)
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        service_with_mock.embed_batch(["Valid text", oversized])

    # 5. Batch preserves input order
    docs = [f"Document number {i} with distinct technical content." for i in range(5)]
    batch_res = service_with_mock.embed_batch(docs)
    assert batch_res.total_documents == 5

    for i in range(5):
        single_res = service_with_mock.embed_text(docs[i])
        # Vector at index i matches single embedding for docs[i]
        assert np.allclose(batch_res.embeddings[i], single_res.embedding, atol=1e-5)


