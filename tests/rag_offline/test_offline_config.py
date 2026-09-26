"""RAG Offline Build 配置兼容与安全默认值测试（唯一测试模块名）。"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.rag_offline import OfflineBuildConfig
from src.rag_offline.config import DEFAULT_MODEL_DIR, DEFAULT_MODEL_REVISION


class OfflineBuildConfigTest(unittest.TestCase):
    def test_existing_local_model_directory_has_priority(self) -> None:
        with TemporaryDirectory() as directory:
            model_dir = Path(directory) / "bge-m3"
            model_dir.mkdir()
            with patch.dict(
                os.environ,
                {
                    "RAG_MODEL_DIR": str(model_dir),
                    "RAG_MODEL_NAME_OR_PATH": "BAAI/remote-model",
                    "RAG_EMBEDDING_DEVICE": "auto",
                    "QDRANT_API_KEY": "local-secret",
                },
                clear=True,
            ):
                config = OfflineBuildConfig.from_environment()

        self.assertEqual(config.model_name_or_path, str(model_dir))
        self.assertIsNone(config.embedding_device)
        self.assertEqual(config.qdrant_api_key, "local-secret")

    def test_legacy_model_id_and_explicit_device_are_supported(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RAG_EMBEDDING_MODEL": "BAAI/bge-m3",
                "RAG_EMBEDDING_DEVICE": "cpu",
            },
            clear=True,
        ):
            config = OfflineBuildConfig.from_environment()

        self.assertEqual(config.model_name_or_path, "BAAI/bge-m3")
        self.assertEqual(config.embedding_device, "cpu")

    def test_default_model_cache_and_revision_are_pinned(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = OfflineBuildConfig.from_environment()

        self.assertEqual(config.model_name_or_path, str(DEFAULT_MODEL_DIR))
        self.assertEqual(config.model_revision, DEFAULT_MODEL_REVISION)
        self.assertEqual(len(config.model_revision), 40)


if __name__ == "__main__":
    unittest.main()
