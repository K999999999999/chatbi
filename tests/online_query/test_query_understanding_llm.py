"""QueryUnderstandingAdapter（查询理解适配器）测试。"""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from src.online_query.llm import LLMError
from src.online_query.query_understanding import (
    QueryType,
    SemanticQueryCandidate,
)
from src.online_query.query_understanding_llm import (
    LangChainQueryUnderstanding,
    QueryUnderstandingAdapter,
    build_query_understanding_prompt,
)


class QueryUnderstandingLLMTest(unittest.TestCase):
    def test_adapter_returns_candidate_from_one_json_object(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(_payload(), ensure_ascii=False)
        )
        adapter = LangChainQueryUnderstanding(model)

        result = adapter.understand("2025 年按客户类型统计销售额")

        self.assertIsInstance(result, SemanticQueryCandidate)
        self.assertEqual(result.query_type, QueryType.METRIC_ANALYSIS)
        self.assertEqual(result.metrics, ("销售额",))
        model.invoke.assert_called_once()
        prompt = model.invoke.call_args.args[0]
        self.assertIn("query_type", prompt)
        self.assertIn("2025 年按客户类型统计销售额", prompt)

    def test_adapter_exposes_query_understanding_protocol(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(_payload(), ensure_ascii=False)
        )

        adapter = LangChainQueryUnderstanding(model)

        self.assertIsInstance(adapter, QueryUnderstandingAdapter)

    def test_prompt_requires_one_object_without_physical_resources(self) -> None:
        prompt = build_query_understanding_prompt("查询销售额")

        self.assertIn("只返回一个 JSON 对象", prompt)
        self.assertIn("subjects", prompt)
        self.assertIn("metrics", prompt)
        self.assertIn("明细行数", prompt)
        self.assertIn("已完成订单数量", prompt)
        self.assertIn("最小指标表达式", prompt)
        self.assertIn("不要输出物理表名、物理字段名", prompt)

    def test_provider_exception_is_controlled_and_not_retried(self) -> None:
        model = Mock()
        model.invoke.side_effect = TimeoutError("provider detail")
        adapter = LangChainQueryUnderstanding(model)

        with self.assertRaisesRegex(LLMError, "Query Understanding LLM 调用失败") as raised:
            adapter.understand("查询销售额")

        self.assertIsInstance(raised.exception.__cause__, TimeoutError)
        self.assertNotIn("provider detail", str(raised.exception))
        model.invoke.assert_called_once()

    def test_empty_non_text_and_invalid_json_are_controlled_errors(self) -> None:
        cases = (
            SimpleNamespace(content="  "),
            SimpleNamespace(content=[{"type": "text"}]),
            SimpleNamespace(content="```json\n{}\n```"),
        )

        for response in cases:
            model = Mock()
            model.invoke.return_value = response
            adapter = LangChainQueryUnderstanding(model)

            with self.subTest(response=response):
                with self.assertRaises(LLMError):
                    adapter.understand("查询销售额")
                model.invoke.assert_called_once()

    def test_invalid_candidate_shape_is_llm_error(self) -> None:
        payload = _payload()
        payload["formula"] = "SUM(amount)"
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(payload, ensure_ascii=False)
        )
        adapter = LangChainQueryUnderstanding(model)

        with self.assertRaisesRegex(LLMError, "结构化输出无效") as raised:
            adapter.understand("查询销售额")

        self.assertNotIn("SUM(amount)", str(raised.exception))

    def test_trace_uses_dedicated_span(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(_payload(), ensure_ascii=False)
        )
        recorder = MagicMock()
        adapter = LangChainQueryUnderstanding(model, trace_recorder=recorder)

        adapter.understand("查询销售额")

        recorder.span.assert_called_once_with(
            "llm.query_understanding",
            attributes=None,
        )

    @patch("src.online_query.query_understanding_llm.ChatOpenAI")
    def test_from_env_reuses_llm_settings_without_retries(
        self,
        chat_open_ai: Mock,
    ) -> None:
        adapter = LangChainQueryUnderstanding.from_env(
            {
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "https://llm.example/v1",
                "LLM_MODEL": "test-model",
                "LLM_TEMPERATURE": "0.1",
                "LLM_MAX_TOKENS": "1200",
                "LLM_TIMEOUT_SECONDS": "30",
            }
        )

        self.assertIsInstance(adapter, LangChainQueryUnderstanding)
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


def _payload() -> dict[str, object]:
    return {
        "query_type": "metric_analysis",
        "subjects": ["销售订单"],
        "metrics": ["销售额"],
        "dimensions": ["客户类型"],
        "time": {"text": "2025年", "granularity": "year"},
        "filters": [],
    }


if __name__ == "__main__":
    unittest.main()
