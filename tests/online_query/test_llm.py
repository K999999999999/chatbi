"""LangChain LLM Adapter（大模型适配器）测试。"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.online_query.llm import LLMError, LangChainSQLGenerator


class LLMTest(unittest.TestCase):
    @patch("src.online_query.llm.ChatOpenAI")
    def test_from_env_configures_timeout_and_disables_retries(
        self,
        chat_open_ai: Mock,
    ) -> None:
        generator = LangChainSQLGenerator.from_env(
            {
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://llm.example/v1",
                "LLM_MODEL": "test-model",
                "LLM_TEMPERATURE": "0.1",
                "LLM_MAX_TOKENS": "1200",
                "LLM_TIMEOUT_SECONDS": "30",
            }
        )

        self.assertIsInstance(generator, LangChainSQLGenerator)
        chat_open_ai.assert_called_once_with(
            api_key="test-key",
            base_url="https://llm.example/v1",
            model="test-model",
            temperature=0.1,
            max_tokens=1200,
            timeout=30.0,
            max_retries=0,
            use_responses_api=False,
        )

    def test_generate_returns_trimmed_sql(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="  SELECT 1;  ")

        result = LangChainSQLGenerator(model).generate("prompt")

        self.assertEqual(result, "SELECT 1;")
        model.invoke.assert_called_once_with("prompt")

    @patch("src.online_query.llm.ChatOpenAI")
    def test_from_env_passes_optional_trace_recorder(self, chat_open_ai: Mock) -> None:
        recorder = Mock()

        generator = LangChainSQLGenerator.from_env(
            {
                "LLM_API_KEY": "test-key",
                "LLM_MODEL": "test-model",
            },
            trace_recorder=recorder,
        )

        self.assertIs(generator._trace_recorder, recorder)

    def test_generate_preserves_cannot_answer(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="CANNOT_ANSWER")

        result = LangChainSQLGenerator(model).generate("prompt")

        self.assertEqual(result, "CANNOT_ANSWER")

    def test_empty_response_is_controlled_error(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="  ")

        with self.assertRaisesRegex(LLMError, "空响应"):
            LangChainSQLGenerator(model).generate("prompt")

    def test_non_text_response_is_controlled_error(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content=[{"type": "text"}])

        with self.assertRaisesRegex(LLMError, "文本"):
            LangChainSQLGenerator(model).generate("prompt")

    def test_provider_exception_is_controlled_error(self) -> None:
        model = Mock()
        model.invoke.side_effect = TimeoutError("provider detail")

        with self.assertRaisesRegex(LLMError, "调用失败") as raised:
            LangChainSQLGenerator(model).generate("prompt")

        self.assertIsInstance(raised.exception.__cause__, TimeoutError)
        self.assertNotIn("provider detail", str(raised.exception))

    def test_missing_required_configuration_is_controlled_error(self) -> None:
        with self.assertRaisesRegex(LLMError, "LLM_API_KEY"):
            LangChainSQLGenerator.from_env({"LLM_MODEL": "test-model"})

    def test_invalid_numeric_configuration_is_controlled_error(self) -> None:
        with self.assertRaisesRegex(LLMError, "配置无效"):
            LangChainSQLGenerator.from_env(
                {
                    "LLM_API_KEY": "test-key",
                    "LLM_MODEL": "test-model",
                    "LLM_TIMEOUT_SECONDS": "not-a-number",
                }
            )

    @patch("src.online_query.llm.ChatOpenAI")
    def test_client_initialization_error_is_controlled(
        self,
        chat_open_ai: Mock,
    ) -> None:
        chat_open_ai.side_effect = ValueError("provider detail")

        with self.assertRaisesRegex(LLMError, "配置无效") as raised:
            LangChainSQLGenerator.from_env(
                {
                    "LLM_API_KEY": "test-key",
                    "LLM_MODEL": "test-model",
                }
            )

        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertNotIn("provider detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
