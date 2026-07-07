"""ChromaDB-backed vector storage and retrieval."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from retriever.embedding import EmbeddingService
from retriever.models import ERPTableMetadata


class ChromaCollectionLike(Protocol):
    """Protocol used to keep the vector store easy to unit test with fakes."""

    def get(
        self,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return raw collection entries."""

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert or update entries."""

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Perform a vector similarity query."""


class ChromaVectorStore:
    """Persists ERP metadata embeddings and serves similarity searches."""

    def __init__(
        self,
        collection_name: str,
        embedding_service: EmbeddingService,
        *,
        persist_directory: Path | None = None,
        collection: ChromaCollectionLike | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.embedding_service = embedding_service
        self.persist_directory = persist_directory
        self._collection = collection

    @property
    def collection(self) -> ChromaCollectionLike:
        """Lazily create or return the underlying Chroma collection."""
        if self._collection is None:
            import chromadb

            if self.persist_directory is not None:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=str(self.persist_directory))
            else:
                client = chromadb.Client()
            self._collection = client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def index_documents(self, documents: Sequence[ERPTableMetadata]) -> int:
        """Incrementally index only new or changed metadata documents."""
        changed_documents = self._filter_changed_documents(documents)
        if not changed_documents:
            return 0

        embeddings = self.embedding_service.embed_documents(changed_documents)
        self.collection.upsert(
            ids=[document.document_id for document in changed_documents],
            documents=[document.to_document_text() for document in changed_documents],
            embeddings=embeddings,
            metadatas=[self._build_storage_metadata(document) for document in changed_documents],
        )
        return len(changed_documents)

    def search(
        self,
        query_text: str,
        *,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run similarity search against indexed ERP metadata with optional filtering."""
        query_embedding = self.embedding_service.embed_text(query_text)
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=metadata_filter,
            include=["documents", "metadatas", "distances"],
        )
        return self._normalize_query_result(result)

    def _filter_changed_documents(
        self,
        documents: Sequence[ERPTableMetadata],
    ) -> list[ERPTableMetadata]:
        """Compare content hashes so unchanged metadata files are skipped during indexing."""
        if not documents:
            return []
        existing = self.collection.get(
            ids=[document.document_id for document in documents],
            include=["metadatas"],
        )
        stored_metadata = {
            document_id: metadata
            for document_id, metadata in zip(
                existing.get("ids", []),
                existing.get("metadatas", []),
                strict=False,
            )
        }
        changed_documents: list[ERPTableMetadata] = []
        for document in documents:
            document_hash = self._hash_document(document)
            stored_hash = (stored_metadata.get(document.document_id) or {}).get("content_hash")
            if stored_hash != document_hash:
                changed_documents.append(document)
        return changed_documents

    def _build_storage_metadata(self, document: ERPTableMetadata) -> dict[str, Any]:
        """Attach filterable metadata plus the content hash used for incremental indexing."""
        metadata = dict(document.to_vector_metadata())
        metadata["columns_json"] = json.dumps([column.name for column in document.columns])
        metadata["relationships_json"] = json.dumps(
            [
                {"table": relationship.table, "join": relationship.join}
                for relationship in document.relationships
            ]
        )
        metadata["content_hash"] = self._hash_document(document)
        return metadata

    def _hash_document(self, document: ERPTableMetadata) -> str:
        """Create a deterministic hash of the flattened document text."""
        return hashlib.sha256(document.to_document_text().encode("utf-8")).hexdigest()

    def _normalize_query_result(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert raw Chroma output into a flatter application-facing structure."""
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        normalized: list[dict[str, Any]] = []
        for document_id, document_text, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=False,
        ):
            normalized_metadata = dict(metadata)
            normalized_metadata["columns"] = json.loads(normalized_metadata.pop("columns_json", "[]"))
            normalized_metadata["relationships"] = json.loads(
                normalized_metadata.pop("relationships_json", "[]")
            )
            normalized.append(
                {
                    "id": document_id,
                    "document": document_text,
                    "metadata": normalized_metadata,
                    "distance": distance,
                }
            )
        return normalized
