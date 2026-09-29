"""RAG source and build configuration provenance tests."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.rag_offline.provenance import build_provenance
from src.rag_offline.sources import load_facts
from tests.rag_offline.test_relationships import _write_facts


class ProvenanceTest(unittest.TestCase):
    def test_fingerprint_is_stable_for_same_source_and_embedding_config(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")
            config = {"provider": "test", "model": "model", "dimension": 4}

            first = build_provenance(facts, config)
            second = build_provenance(facts, dict(reversed(tuple(config.items()))))

        self.assertEqual(first, second)

    def test_metadata_file_change_changes_structure_fingerprint(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            first = build_provenance(load_facts(root, root / "metrics.json"), {})

            columns_path = root / "columns.json"
            columns = json.loads(columns_path.read_text(encoding="utf-8"))
            columns[0]["ordinal_position"] = 1
            columns_path.write_text(
                json.dumps(columns, ensure_ascii=False),
                encoding="utf-8",
            )
            second = build_provenance(load_facts(root, root / "metrics.json"), {})

        self.assertNotEqual(
            first["schema_metadata_sha256"],
            second["schema_metadata_sha256"],
        )

    def test_metric_or_embedding_change_changes_its_fingerprint(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")
            first = build_provenance(
                facts,
                {"provider": "test", "model": "model", "dimension": 4},
            )
            metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
            metrics[0]["definition"] = "updated definition"
            (root / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False),
                encoding="utf-8",
            )
            changed_metrics = load_facts(root, root / "metrics.json")
            second = build_provenance(
                changed_metrics,
                {"provider": "test", "model": "model", "dimension": 4},
            )
            third = build_provenance(
                changed_metrics,
                {"provider": "test", "model": "model", "dimension": 8},
            )

        self.assertNotEqual(first["metrics_sha256"], second["metrics_sha256"])
        self.assertNotEqual(
            second["embedding_config_sha256"],
            third["embedding_config_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
