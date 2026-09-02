"""Query API 启动配置加载测试。"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.query_api.config import load_local_environment


class QueryApiConfigTest(unittest.TestCase):
    def test_loads_explicit_env_file(self) -> None:
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "CHATBI_TEST_ENV_FILE_VALUE=from-file\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CHATBI_TEST_ENV_FILE_VALUE", None)
                load_local_environment(env_file)

                self.assertEqual(
                    os.environ["CHATBI_TEST_ENV_FILE_VALUE"],
                    "from-file",
                )

    def test_existing_environment_value_is_not_overridden(self) -> None:
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "CHATBI_TEST_ENV_PRIORITY=from-file\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"CHATBI_TEST_ENV_PRIORITY": "from-process"},
                clear=False,
            ):
                load_local_environment(env_file)

                self.assertEqual(
                    os.environ["CHATBI_TEST_ENV_PRIORITY"],
                    "from-process",
                )

    def test_missing_env_file_is_allowed(self) -> None:
        with TemporaryDirectory() as directory:
            missing_file = Path(directory) / ".env"

            load_local_environment(missing_file)


if __name__ == "__main__":
    unittest.main()
