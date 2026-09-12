"""Observability 配置的确定性安全规则测试。"""

import unittest

from src.observability.config import ObservabilityConfig


class ObservabilityConfigTest(unittest.TestCase):
    def test_content_capture_is_fail_closed_by_default_and_unknown_env(self) -> None:
        default_config = ObservabilityConfig.from_env({})
        unknown_config = ObservabilityConfig.from_env(
            {
                "CHATBI_RUNTIME_ENV": "qa",
                "CHATBI_TRACE_CONTENT_ENABLED": "true",
            }
        )
        production_config = ObservabilityConfig.from_env(
            {
                "CHATBI_RUNTIME_ENV": "production",
                "CHATBI_TRACE_CONTENT_ENABLED": "true",
            }
        )

        self.assertFalse(default_config.content_capture_enabled)
        self.assertFalse(unknown_config.content_capture_enabled)
        self.assertFalse(production_config.content_capture_enabled)

    def test_content_capture_requires_explicit_local_environment(self) -> None:
        for runtime_env in ("local", "DEV", "test"):
            config = ObservabilityConfig.from_env(
                {
                    "CHATBI_RUNTIME_ENV": runtime_env,
                    "CHATBI_TRACE_CONTENT_ENABLED": "true",
                }
            )
            self.assertTrue(config.content_capture_enabled, runtime_env)

        disabled = ObservabilityConfig.from_env(
            {
                "CHATBI_RUNTIME_ENV": "local",
                "CHATBI_TRACE_CONTENT_ENABLED": "false",
            }
        )
        conflict = ObservabilityConfig.from_env(
            {
                "CHATBI_RUNTIME_ENV": "local",
                "CHATBI_TRACE_CONTENT_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": (
                    "deployment.environment.name=production"
                ),
            }
        )

        self.assertFalse(disabled.content_capture_enabled)
        self.assertFalse(conflict.content_capture_enabled)

        duplicate_conflict = ObservabilityConfig.from_env(
            {
                "CHATBI_RUNTIME_ENV": "local",
                "CHATBI_TRACE_CONTENT_ENABLED": "true",
                "OTEL_RESOURCE_ATTRIBUTES": (
                    "deployment.environment.name=local,"
                    "deployment.environment.name=production"
                ),
            }
        )
        self.assertFalse(duplicate_conflict.content_capture_enabled)

    def test_direct_construction_is_fail_closed(self) -> None:
        for runtime_env in ("local", "DEV", "test"):
            with self.subTest(runtime_env=runtime_env):
                config = ObservabilityConfig(
                    runtime_env=runtime_env,
                    content_capture_enabled=True,
                )
                self.assertTrue(config.content_capture_enabled)

        for runtime_env in (None, "production", "staging", "unknown"):
            with self.subTest(runtime_env=runtime_env):
                config = ObservabilityConfig(
                    runtime_env=runtime_env,
                    content_capture_enabled=True,
                )
                self.assertFalse(config.content_capture_enabled)

        for deployment_environment in ("production", "staging", "unknown"):
            with self.subTest(deployment_environment=deployment_environment):
                config = ObservabilityConfig(
                    runtime_env="local",
                    deployment_environment=deployment_environment,
                    content_capture_enabled=True,
                )
                self.assertFalse(config.content_capture_enabled)

        case_insensitive = ObservabilityConfig(
            runtime_env="DEV",
            deployment_environment="dev",
            content_capture_enabled=True,
        )
        self.assertTrue(case_insensitive.content_capture_enabled)

    def test_otlp_timeout_and_headers_are_parsed_without_defaults_leaking(self) -> None:
        config = ObservabilityConfig.from_env(
            {
                "CHATBI_OBSERVABILITY_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://collector/v1/traces",
                "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer secret,tenant=t1",
                "CHATBI_OTLP_TIMEOUT_SECONDS": "2.5",
            }
        )
        invalid_timeout = ObservabilityConfig.from_env(
            {"CHATBI_OTLP_TIMEOUT_SECONDS": "not-a-number"}
        )

        self.assertTrue(config.enabled)
        self.assertEqual(config.otlp_timeout_seconds, 2.5)
        self.assertEqual(config.otlp_endpoint, "http://collector/v1/traces")
        self.assertEqual(config.otlp_headers["tenant"], "t1")
        self.assertEqual(invalid_timeout.otlp_timeout_seconds, 5.0)


if __name__ == "__main__":
    unittest.main()
