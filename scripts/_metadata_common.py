"""Shared helpers for metadata extraction, enrichment, and embedding scripts."""

from __future__ import annotations

import logging
from pathlib import Path

from config import get_config
from database.oracle import OracleDatabaseClient
from retriever.embedding import EmbeddingService
from retriever.vector_store import ChromaVectorStore
from services.metadata_loader import MetadataLoader
from services.metadata_repository import MetadataRepository
from services.oracle_metadata_service import OracleMetadataService


def configure_logging() -> None:
    """Configure a simple console logger for metadata scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def build_repository(metadata_root: Path | None = None) -> MetadataRepository:
    """Create a repository rooted at the default or supplied metadata directory."""
    root = metadata_root or (Path(__file__).resolve().parent.parent / "metadata")
    repository = MetadataRepository(root)
    repository.ensure_structure()
    return repository


def build_oracle_metadata_service() -> OracleMetadataService:
    """Create the Oracle metadata extraction service using the shared app config."""
    config = get_config()
    return OracleMetadataService(OracleDatabaseClient(config.oracle))


def build_metadata_loader(repository: MetadataRepository) -> MetadataLoader:
    """Create the metadata loader and enrichment adapter service."""
    return MetadataLoader(repository)


def build_vector_store(metadata_root: Path | None = None) -> ChromaVectorStore:
    """Create a Chroma vector store rooted under metadata/embeddings."""
    config = get_config()
    repository = build_repository(metadata_root)
    embeddings_dir = repository.embeddings_dir / "chromadb"
    embedding_service = EmbeddingService(
        model_name=config.embedding.model_name,
        device=config.embedding.device,
    )
    return ChromaVectorStore(
        collection_name="erp_metadata_enterprise",
        embedding_service=embedding_service,
        persist_directory=embeddings_dir,
    )
