"""Enrich raw Oracle ERP metadata with business-friendly knowledge."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts._metadata_common import build_metadata_loader, build_repository, configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Load raw metadata, enrich it, and save enriched JSON files."""
    parser = argparse.ArgumentParser(description="Enrich raw metadata into metadata/enriched.")
    parser.add_argument("--metadata-root", default=None, help="Optional metadata root directory.")
    args = parser.parse_args()

    configure_logging()
    repository = build_repository(Path(args.metadata_root) if args.metadata_root else None)
    loader = build_metadata_loader(repository)

    raw_tables = loader.load_raw_tables()
    enriched_tables = loader.enrich_tables(raw_tables)
    for table in enriched_tables:
        repository.save_enriched_table(table)
    for payload in loader.build_agent_payloads(enriched_tables):
        repository.save_agent_ready_payload(payload["table"], payload)

    report = loader.validate_tables(enriched_tables)
    repository.save_validation_report(report)
    LOGGER.info("Saved %s enriched metadata tables to %s", len(enriched_tables), repository.enriched_dir)
    LOGGER.info("Saved %s agent-ready metadata tables to %s", len(enriched_tables), repository.agent_ready_dir)
    return 0 if report["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
