"""Sentence Transformer embedding service."""

from __future__ import annotations

from collections.abc import Sequence
import gc
from typing import Any, Protocol

from retriever.models import ERPTableMetadata


class SentenceTransformerLike(Protocol):
    """Test-friendly protocol representing the subset of SentenceTransformer we use."""

    def encode(
        self,
        sentences: str | Sequence[str],
        **kwargs: Any,
    ) -> Any:
        """Encode one or more strings into embedding vectors."""


class EmbeddingService:
    """Encodes ERP metadata and user questions into embedding vectors."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        model: SentenceTransformerLike | None = None,
        *,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self._model = model

    @property
    def model(self) -> SentenceTransformerLike:
        """Lazily load the Sentence Transformers model the first time it is needed."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            if self.device:
                self._model = SentenceTransformer(self.model_name, device=self.device)
            else:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string and return a plain Python list for storage and search."""
        vector = self.model.encode(
            text,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        return vector.tolist()

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed many strings in one batch for efficient indexing."""
        if not texts:
            return []
        vectors = self.model.encode(
            list(texts),
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def embed_documents(self, documents: Sequence[ERPTableMetadata]) -> list[list[float]]:
        """Embed metadata documents using their flattened text representation."""
        return self.embed_texts([document.to_document_text() for document in documents])

    def close(self) -> None:
        """Release the embedding model and clear cached CUDA memory."""
        self._model = None
        gc.collect()
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
