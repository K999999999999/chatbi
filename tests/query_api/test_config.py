"""Query API 启动配置加载测试。"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.authorization import AuthContext
from src.query_api.config import (
    AuthorizationPolicyConfigurationError,
    IdentityProviderConfigurationError,
    build_identity_provider,
    build_policy_store,
    load_local_environment,
)


class QueryApiConfigTest(unittest.TestCase):
    def test_builds_explicit_test_identity_provider(self) -> None:
        provider = build_identity_provider(
            {
                "CHATBI_ENV": "development",
                "CHATBI_IDENTITY_PROVIDER": "test",
                "CHATBI_IDENTITY_SUBJECT_ID": "analyst-1",
            }
        )

        auth_context = provider.authenticate()

        self.assertEqual(auth_context, AuthContext("analyst-1", "test"))

    def test_rejects_demo_identity_provider_in_production(self) -> None:
        with self.assertRaises(IdentityProviderConfigurationError):
            build_identity_provider(
                {
                    "CHATBI_ENV": "production",
                    "CHATBI_IDENTITY_PROVIDER": "demo",
                    "CHATBI_IDENTITY_SUBJECT_ID": "recruiter-demo",
                }
            )

    def test_rejects_missing_identity_provider_configuration(self) -> None:
        with self.assertRaises(IdentityProviderConfigurationError):
            build_identity_provider(
                {
                    "CHATBI_ENV": "development",
                    "CHATBI_IDENTITY_SUBJECT_ID": "analyst-1",
                }
            )

    def test_rejects_missing_runtime_environment_configuration(self) -> None:
        with self.assertRaises(IdentityProviderConfigurationError):
            build_identity_provider(
                {
                    "CHATBI_IDENTITY_PROVIDER": "test",
                    "CHATBI_IDENTITY_SUBJECT_ID": "analyst-1",
                }
            )

    def test_builds_static_policy_from_external_json_file(self) -> None:
        with TemporaryDirectory() as directory:
            policy_file = Path(directory) / "authorization.json"
            policy_file.write_text(
                '{"policy_version":"policy-v1","allowed_subjects":["analyst-1"]}',
                encoding="utf-8",
            )

            store = build_policy_store({"CHATBI_AUTH_POLICY_FILE": str(policy_file)})

        decision = store.authorize(
            AuthContext("analyst-1", "test"),
            resource="mart_sales",
            action="query",
            mode="read_only",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.policy_version, "policy-v1")

    def test_rejects_missing_or_invalid_policy_file(self) -> None:
        with self.assertRaises(AuthorizationPolicyConfigurationError):
            build_policy_store({})

        with TemporaryDirectory() as directory:
            policy_file = Path(directory) / "invalid.json"
            policy_file.write_text("[]", encoding="utf-8")

            with self.assertRaises(AuthorizationPolicyConfigurationError):
                build_policy_store({"CHATBI_AUTH_POLICY_FILE": str(policy_file)})

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
