"""Unit tests for embeddings and Chroma vector indexing behavior."""

from __future__ import annotations

import unittest

from retriever.embedding import EmbeddingService
from retriever.models import ERPColumnMetadata, ERPRelationshipMetadata, ERPTableMetadata
from retriever.vector_store import ChromaVectorStore


class FakeVector:
    """Minimal vector object exposing the interface returned by numpy arrays."""

    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class FakeMatrix:
    """Minimal matrix object exposing the interface returned by numpy arrays."""

    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def tolist(self) -> list[list[float]]:
        return [list(row) for row in self._rows]


class FakeSentenceTransformer:
    """Simple fake model that returns deterministic embeddings."""

    def encode(self, sentences, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(sentences, str):
            return FakeVector([float(len(sentences)), 1.0])
        return FakeMatrix([[float(len(sentence)), 1.0] for sentence in sentences])


class FakeCollection:
    """In-memory fake Chroma collection for unit testing."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}

    def get(self, ids=None, where=None, include=None):  # type: ignore[no-untyped-def]
        if ids is None:
            ids = list(self.records)
        metadatas = [self.records[item_id]["metadata"] for item_id in ids if item_id in self.records]
        found_ids = [item_id for item_id in ids if item_id in self.records]
        return {"ids": found_ids, "metadatas": metadatas}

    def upsert(self, *, ids, documents, embeddings, metadatas):  # type: ignore[no-untyped-def]
        for item_id, document, embedding, metadata in zip(
            ids,
            documents,
            embeddings,
            metadatas,
            strict=False,
        ):
            self.records[item_id] = {
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def query(self, *, query_embeddings, n_results, where=None, include=None):  # type: ignore[no-untyped-def]
        rows = []
        module_filter = (where or {}).get("module") if where else None
        for item_id, record in self.records.items():
            metadata = record["metadata"]
            if module_filter and metadata["module"] != module_filter:
                continue
            rows.append(
                {
                    "id": item_id,
                    "document": record["document"],
                    "metadata": metadata,
                    "distance": 0.01,
                }
            )
        rows = rows[:n_results]
        return {
            "ids": [[row["id"] for row in rows]],
            "documents": [[row["document"] for row in rows]],
            "metadatas": [[row["metadata"] for row in rows]],
            "distances": [[row["distance"] for row in rows]],
        }


def build_document(table: str, module: str = "Accounts Payable") -> ERPTableMetadata:
    """Create a reusable metadata document for tests."""
    return ERPTableMetadata(
        module=module,
        table=table,
        description=f"Description for {table}",
        primary_key="ID",
        columns=(ERPColumnMetadata(name="ID", description="Identifier"),),
        relationships=(ERPRelationshipMetadata(table="OTHER_TABLE", join="ID"),),
        business_questions=("Show records",),
    )


class VectorStoreTests(unittest.TestCase):
    """Verifies incremental indexing and filtered retrieval behavior."""

    def test_incremental_indexing_skips_unchanged_documents(self) -> None:
        embedding_service = EmbeddingService(model=FakeSentenceTransformer())
        collection = FakeCollection()
        vector_store = ChromaVectorStore(
            collection_name="erp_metadata",
            embedding_service=embedding_service,
            collection=collection,
        )

        document = build_document("AP_INVOICES_ALL")
        first_indexed = vector_store.index_documents([document])
        second_indexed = vector_store.index_documents([document])

        self.assertEqual(1, first_indexed)
        self.assertEqual(0, second_indexed)

    def test_search_returns_filtered_top_k_results(self) -> None:
        embedding_service = EmbeddingService(model=FakeSentenceTransformer())
        collection = FakeCollection()
        vector_store = ChromaVectorStore(
            collection_name="erp_metadata",
            embedding_service=embedding_service,
            collection=collection,
        )
        vector_store.index_documents(
            [
                build_document("AP_INVOICES_ALL", module="Accounts Payable"),
                build_document("RA_CUSTOMER_TRX_ALL", module="Accounts Receivable"),
            ]
        )

        results = vector_store.search(
            "customer invoices",
            top_k=5,
            metadata_filter={"module": "Accounts Receivable"},
        )

        self.assertEqual(1, len(results))
        self.assertEqual("Accounts Receivable::RA_CUSTOMER_TRX_ALL", results[0]["id"])


if __name__ == "__main__":
    unittest.main()
