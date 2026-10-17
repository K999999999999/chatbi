"""Safe provider failure classification (Provider 故障分类) tests."""

import unittest

from src.observability.failure_diagnostics import provider_failure_attributes
from src.observability.tracing_safety import safe_attributes


class ProviderFailureDiagnosticsTest(unittest.TestCase):
    def test_timeout_in_cause_chain_is_classified_without_exception_text(self) -> None:
        inner = TimeoutError("private provider detail")
        wrapper = ConnectionError("private wrapper detail")
        wrapper.__cause__ = inner

        attributes = provider_failure_attributes(wrapper)

        self.assertEqual(attributes["chatbi.provider.error_category"], "TIMEOUT")
        self.assertTrue(attributes["chatbi.provider.retryable"])
        self.assertNotIn("private", repr(attributes))
        self.assertNotIn("TimeoutError", repr(attributes))
        self.assertNotIn("ConnectionError", repr(attributes))

    def test_rate_limit_status_is_classified_and_bounded(self) -> None:
        class ProviderStatusError(Exception):
            status_code = 429

        attributes = provider_failure_attributes(
            ProviderStatusError("private response body")
        )

        self.assertEqual(
            attributes,
            {
                "chatbi.provider.error_category": "RATE_LIMITED",
                "chatbi.provider.http_status_code": 429,
                "chatbi.provider.retryable": True,
            },
        )

    def test_unknown_provider_error_does_not_emit_exception_details(self) -> None:
        class PrivateProviderError(Exception):
            pass

        attributes = provider_failure_attributes(
            PrivateProviderError("private response body")
        )

        self.assertEqual(attributes, {"chatbi.provider.error_category": "UNKNOWN"})
        self.assertNotIn("PrivateProviderError", repr(attributes))
        self.assertNotIn("private response body", repr(attributes))

    def test_invalid_http_status_is_not_exported(self) -> None:
        class InvalidStatusError(Exception):
            status_code = 999

        attributes = provider_failure_attributes(InvalidStatusError("private"))

        self.assertEqual(attributes, {"chatbi.provider.error_category": "UNKNOWN"})

    def test_trace_filter_accepts_only_fixed_failure_categories(self) -> None:
        attributes = safe_attributes(
            {
                "chatbi.provider.error_category": "TIMEOUT",
                "chatbi.provider.http_status_code": 429,
                "chatbi.provider.retryable": True,
                "chatbi.sql_guard.rejection_code": "METRIC_CONSTRAINT_REJECTED",
            }
        )
        self.assertEqual(len(attributes), 4)

        rejected = safe_attributes(
            {
                "chatbi.provider.error_category": "private provider error",
                "chatbi.provider.http_status_code": 999,
                "chatbi.provider.retryable": "yes",
                "chatbi.sql_guard.rejection_code": "SQL rejected: private data",
            }
        )
        self.assertEqual(rejected, {})


if __name__ == "__main__":
    unittest.main()
