"""Unit tests for metadata loading and search."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from retriever.exceptions import MetadataValidationError
from retriever.schema_loader import SchemaLoader


VALID_METADATA = {
    "module": "Accounts Payable",
    "table": "AP_INVOICES_ALL",
    "description": "Stores supplier invoices",
    "primary_key": "INVOICE_ID",
    "columns": [
        {"name": "INVOICE_ID", "description": "Invoice Identifier"},
        {"name": "VENDOR_ID", "description": "Supplier Identifier"},
    ],
    "relationships": [
        {"table": "AP_SUPPLIERS", "join": "VENDOR_ID"},
    ],
    "business_questions": [
        "Show unpaid invoices",
        "Invoices by supplier",
    ],
}


class SchemaLoaderTests(unittest.TestCase):
    """Verifies schema validation, loading, and search helpers."""

    def test_load_converts_json_to_dataclass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata_path = Path(tmp_dir) / "ap_invoices_all.json"
            metadata_path.write_text(json.dumps(VALID_METADATA), encoding="utf-8")

            loader = SchemaLoader()
            documents = loader.load(Path(tmp_dir))

            self.assertEqual(1, len(documents))
            self.assertEqual("AP_INVOICES_ALL", documents[0].table)
            self.assertEqual("Accounts Payable", documents[0].module)
            self.assertEqual(metadata_path, documents[0].source_path)

    def test_load_raises_for_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata_path = Path(tmp_dir) / "broken.json"
            broken_payload = dict(VALID_METADATA)
            broken_payload.pop("columns")
            metadata_path.write_text(json.dumps(broken_payload), encoding="utf-8")

            loader = SchemaLoader()
            with self.assertRaises(MetadataValidationError):
                loader.load(Path(tmp_dir))

    def test_search_and_module_filter_are_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            metadata_path = Path(tmp_dir) / "ap_invoices_all.json"
            metadata_path.write_text(json.dumps(VALID_METADATA), encoding="utf-8")

            loader = SchemaLoader()
            loader.load(Path(tmp_dir))

            by_table = loader.get_by_table("ap_invoices_all")
            by_module = loader.filter_by_module("accounts payable")
            by_search = loader.search("supplier", module="Accounts Payable")

            self.assertIsNotNone(by_table)
            self.assertEqual(1, len(by_module))
            self.assertEqual(1, len(by_search))


if __name__ == "__main__":
    unittest.main()
