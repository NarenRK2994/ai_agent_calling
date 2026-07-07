"""Extract raw Oracle ERP metadata from the Oracle Data Dictionary."""

from __future__ import annotations

import argparse
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
    configure_logging,
)


LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Extract raw Oracle metadata and save one JSON file per table."""
    parser = argparse.ArgumentParser(description="Extract Oracle ERP metadata into metadata/raw.")
    parser.add_argument("--owner", default=None, help="Optional Oracle owner/schema filter, for example APPS.")
    parser.add_argument("--metadata-root", default=None, help="Optional metadata root directory.")
    args = parser.parse_args()

    configure_logging()
    repository = build_repository(Path(args.metadata_root) if args.metadata_root else None)
    loader = build_metadata_loader(repository)
    service = build_oracle_metadata_service()

    tables = service.extract_tables(owner=args.owner)
    for table in tables:
        repository.save_raw_table(table)

    report = loader.validate_tables(tables)
    repository.save_validation_report(report)
    LOGGER.info("Saved %s raw metadata tables to %s", len(tables), repository.raw_dir)
    LOGGER.info("Validation report: %s", report["is_valid"])
    return 0 if report["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
