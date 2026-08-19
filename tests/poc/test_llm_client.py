"""OpenAI-compatible LLM Client（大模型客户端）协议测试。"""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from src.poc.config import LlmConfig
from src.poc.llm_client import OpenAICompatibleLlmClient, SqlGenerationError


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object):  # type: ignore[no-untyped-def]
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))


class LlmClientTest(unittest.TestCase):
    def test_markdown_sql_is_cleaned_and_request_is_direct(self) -> None:
        fake = _FakeClient(
            "```sql\nSELECT 1 FROM mart_sales.dim_date\n```"
        )
        client = OpenAICompatibleLlmClient(
            LlmConfig(
                api_key="test-key",
                base_url="https://example.test/v1",
                model="test-model",
            ),
            client=fake,
        )

        sql = client.generate_sql("system", "question")

        self.assertEqual("SELECT 1 FROM mart_sales.dim_date", sql)
        request = fake.chat.completions.kwargs
        self.assertEqual("test-model", request["model"])
        self.assertEqual(0.1, request["temperature"])
        self.assertEqual(1200, request["max_tokens"])
        self.assertEqual("system", request["messages"][0]["content"])
        self.assertEqual("question", request["messages"][1]["content"])

    def test_unsupported_sentinel_is_controlled_failure(self) -> None:
        client = OpenAICompatibleLlmClient(
            LlmConfig(
                api_key="test-key",
                base_url="https://example.test/v1",
                model="test-model",
            ),
            client=_FakeClient("UNSUPPORTED"),
        )

        with self.assertRaisesRegex(SqlGenerationError, "超出"):
            client.generate_sql("system", "question")


if __name__ == "__main__":
    unittest.main()
