"""Repository helpers for raw, enriched, cached, and embedded metadata artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from metadata_models import TableMetadata


class MetadataRepository:
    """Persists metadata artifacts to a structured filesystem layout."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.raw_dir = root_dir / "raw"
        self.enriched_dir = root_dir / "enriched"
        self.agent_ready_dir = root_dir / "agent_ready"
        self.embeddings_dir = root_dir / "embeddings"
        self.cache_dir = root_dir / "cache"

    def ensure_structure(self) -> None:
        """Create the metadata directory structure when it does not yet exist."""
        for directory in (
            self.root_dir,
            self.raw_dir,
            self.enriched_dir,
            self.agent_ready_dir,
            self.embeddings_dir,
            self.cache_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def save_raw_table(self, table_metadata: TableMetadata) -> Path:
        """Persist one raw table metadata file under the raw directory."""
        return self._write_json(self.raw_dir / f"{table_metadata.table}.json", table_metadata.to_dict())

    def save_enriched_table(self, table_metadata: TableMetadata) -> Path:
        """Persist one enriched table metadata file under the enriched directory."""
        return self._write_json(
            self.enriched_dir / f"{table_metadata.table}.json",
            table_metadata.to_dict(),
        )

    def load_raw_payloads(self) -> list[dict[str, Any]]:
        """Load all raw metadata payloads from disk."""
        return self._load_payloads(self.raw_dir)

    def load_enriched_payloads(self) -> list[dict[str, Any]]:
        """Load all enriched metadata payloads from disk."""
        return self._load_payloads(self.enriched_dir)

    def save_agent_ready_payload(self, table_name: str, payload: dict[str, Any]) -> Path:
        """Persist one legacy-compatible agent metadata JSON file."""
        return self._write_json(self.agent_ready_dir / f"{table_name}.json", payload)

    def save_validation_report(self, report: dict[str, Any]) -> Path:
        """Persist the latest validation report under the cache directory."""
        return self._write_json(self.cache_dir / "validation_report.json", report)

    def load_cached_hashes(self) -> dict[str, str]:
        """Load previously stored content hashes for incremental refresh."""
        path = self.cache_dir / "content_hashes.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_cached_hashes(self, hashes: dict[str, str]) -> Path:
        """Persist current content hashes for incremental refresh decisions."""
        return self._write_json(self.cache_dir / "content_hashes.json", hashes)

    def build_hash(self, payload: dict[str, Any]) -> str:
        """Create a deterministic content hash for a metadata payload."""
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def has_changed(self, table_name: str, payload: dict[str, Any], cached_hashes: dict[str, str]) -> bool:
        """Return true when a table payload differs from the cached content hash."""
        return cached_hashes.get(table_name.upper()) != self.build_hash(payload)

    def save_embedding_manifest(self, manifest: dict[str, Any]) -> Path:
        """Persist embedding build details for auditing and refresh tracking."""
        return self._write_json(self.embeddings_dir / "manifest.json", manifest)

    def _load_payloads(self, directory: Path) -> list[dict[str, Any]]:
        """Load all JSON payloads from the target directory in deterministic order."""
        if not directory.exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        """Write JSON to disk with stable formatting."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return path
