"""Incrementally refresh raw metadata, enrichment, validation, and embeddings."""

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

from scripts._metadata_common import (
    build_metadata_loader,
    build_oracle_metadata_service,
    build_repository,
    build_vector_store,
    configure_logging,
)


LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Refresh only changed metadata tables and rebuild embeddings incrementally."""
    parser = argparse.ArgumentParser(description="Incrementally refresh Oracle ERP metadata.")
    parser.add_argument("--owner", default=None, help="Optional Oracle owner/schema filter.")
    parser.add_argument("--metadata-root", default=None, help="Optional metadata root directory.")
    args = parser.parse_args()

    configure_logging()
    metadata_root = Path(args.metadata_root) if args.metadata_root else None
    repository = build_repository(metadata_root)
    loader = build_metadata_loader(repository)
    service = build_oracle_metadata_service()
    vector_store = build_vector_store(metadata_root)

    cached_hashes = repository.load_cached_hashes()
    extracted_tables = service.extract_tables(owner=args.owner)
    changed_tables = []
    next_hashes: dict[str, str] = {}
    for table in extracted_tables:
        payload = table.to_dict()
        table_hash = repository.build_hash(payload)
        next_hashes[table.table] = table_hash
        if repository.has_changed(table.table, payload, cached_hashes):
            repository.save_raw_table(table)
            changed_tables.append(table)

    if not changed_tables:
        LOGGER.info("No metadata changes detected. Embedding rebuild skipped.")
        return 0

    enriched_tables = loader.enrich_tables(changed_tables)
    for table in enriched_tables:
        repository.save_enriched_table(table)
    for payload in loader.build_agent_payloads(enriched_tables):
        repository.save_agent_ready_payload(payload["table"], payload)

    all_enriched_tables = loader.load_enriched_tables()
    for payload in loader.build_agent_payloads(all_enriched_tables):
        repository.save_agent_ready_payload(payload["table"], payload)
    report = loader.validate_tables(all_enriched_tables)
    repository.save_validation_report(report)
    repository.save_cached_hashes(next_hashes)

    agent_documents = loader.build_agent_documents(all_enriched_tables)
    indexed_count = vector_store.index_documents(agent_documents)
    repository.save_embedding_manifest(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "changed_tables": [table.table for table in changed_tables],
            "indexed_count": indexed_count,
            "table_count": len(all_enriched_tables),
        }
    )
    LOGGER.info("Refreshed %s changed tables and indexed %s documents", len(changed_tables), indexed_count)
    return 0 if report["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
