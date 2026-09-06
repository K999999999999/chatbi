"""RAG Offline Build 配置兼容与安全默认值测试（唯一测试模块名）。"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.rag_offline import OfflineBuildConfig


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


if __name__ == "__main__":
    unittest.main()
