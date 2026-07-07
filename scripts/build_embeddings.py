"""Build or refresh ChromaDB embeddings from enriched metadata."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts._metadata_common import build_metadata_loader, build_repository, build_vector_store, configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Generate searchable metadata documents and index them into ChromaDB."""
    parser = argparse.ArgumentParser(description="Build embeddings from enriched metadata.")
    parser.add_argument("--metadata-root", default=None, help="Optional metadata root directory.")
    args = parser.parse_args()

    configure_logging()
    metadata_root = Path(args.metadata_root) if args.metadata_root else None
    repository = build_repository(metadata_root)
    loader = build_metadata_loader(repository)
    vector_store = build_vector_store(metadata_root)

    enriched_tables = loader.load_enriched_tables()
    agent_documents = loader.build_agent_documents(enriched_tables)
    indexed_count = vector_store.index_documents(agent_documents)
    repository.save_embedding_manifest(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "table_count": len(enriched_tables),
            "indexed_count": indexed_count,
            "collection_name": vector_store.collection_name,
        }
    )
    LOGGER.info("Indexed %s changed metadata documents into ChromaDB", indexed_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
