"""Retriever orchestration for ERP schema search."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever as LangChainBaseRetriever
from pydantic import ConfigDict

from retriever.base import BaseRetriever
from retriever.schema_loader import SchemaLoader
from retriever.vector_store import ChromaVectorStore


class ERPMetadataRetriever(BaseRetriever):
    """Coordinates schema loading, indexing, and filtered similarity retrieval."""

    def __init__(
        self,
        schema_loader: SchemaLoader,
        vector_store: ChromaVectorStore,
    ) -> None:
        self.schema_loader = schema_loader
        self.vector_store = vector_store

    def index_metadata(self) -> int:
        """Index the metadata already loaded into the schema loader."""
        documents = self.schema_loader.list_documents()
        return self.vector_store.index_documents(documents)

    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top-k most similar metadata entries for a user query."""
        return self.vector_store.search(query, top_k=top_k, metadata_filter=filters)


class LangChainSchemaRetriever(LangChainBaseRetriever):
    """LangChain-compatible retriever that wraps the ERP metadata vector store."""

    vector_store: ChromaVectorStore
    default_top_k: int = 5
    default_filters: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(self, query: str, *, run_manager: Any = None) -> list[Document]:
        """Return LangChain documents for the highest-similarity ERP table matches."""
        results = self.vector_store.search(
            query,
            top_k=self.default_top_k,
            metadata_filter=self.default_filters,
        )
        return [self._result_to_document(result) for result in results]

    def retrieve_with_scores(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw retrieval results including metadata and similarity scores."""
        results = self.vector_store.search(
            query,
            top_k=top_k or self.default_top_k,
            metadata_filter=filters if filters is not None else self.default_filters,
        )
        return [
            {
                "table": result["metadata"]["table"],
                "module": result["metadata"]["module"],
                "relationships": result["metadata"].get("relationships", []),
                "columns": result["metadata"].get("columns", []),
                "primary_key": result["metadata"].get("primary_key"),
                "similarity_score": self._distance_to_similarity(result["distance"]),
                "source_path": result["metadata"].get("source_path", ""),
                "document": result["document"],
            }
            for result in results
        ]

    def _result_to_document(self, result: dict[str, Any]) -> Document:
        """Convert one vector-store match into a LangChain document instance."""
        metadata = dict(result["metadata"])
        metadata["similarity_score"] = self._distance_to_similarity(result["distance"])
        return Document(page_content=result["document"], metadata=metadata)

    def _distance_to_similarity(self, distance: float | None) -> float:
        """Convert a Chroma distance value into an easy-to-read similarity score."""
        if distance is None:
            return 0.0
        return max(0.0, 1.0 - float(distance))
