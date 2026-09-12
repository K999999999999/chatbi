"""T3B LLM Generation 属性和安全边界的独立确定性测试。"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from src.observability.contracts import QuerySource
from src.observability.tracing import create_in_memory_recorder
from src.online_query.llm import LangChainSQLGenerator


class T3BObservabilityTest(unittest.TestCase):
    def test_standard_genai_attributes_use_existing_llm_span(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content="SELECT 1",
            response_metadata={"model_name": "provider-model"},
            usage_metadata={
                "input_tokens": 11,
                "output_tokens": 7,
                "total_tokens": 18,
            },
        )
        recorder, exporter = create_in_memory_recorder()
        generator = LangChainSQLGenerator(
            model,
            trace_recorder=recorder,
            model_name="request-model",
        )

        with recorder.query_trace(QuerySource.INTERNAL):
            with recorder.span("llm.generate"):
                self.assertEqual(generator.generate("PROMPT-CONTENT"), "SELECT 1")

        spans = exporter.get_finished_spans()
        llm_spans = [span for span in spans if span.name == "llm.generate"]
        self.assertEqual(len(llm_spans), 1)
        attributes = llm_spans[0].attributes
        self.assertEqual(attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(attributes["gen_ai.request.model"], "request-model")
        self.assertEqual(attributes["gen_ai.response.model"], "provider-model")
        self.assertEqual(attributes["gen_ai.usage.input_tokens"], 11)
        self.assertEqual(attributes["gen_ai.usage.output_tokens"], 7)
        self.assertEqual(attributes["gen_ai.usage.total_tokens"], 18)

    def test_response_model_accepts_provider_model_alias(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content="SELECT 1",
            response_metadata={"model": "provider-alias"},
        )
        recorder, exporter = create_in_memory_recorder()
        generator = LangChainSQLGenerator(model, trace_recorder=recorder)

        with recorder.query_trace(QuerySource.INTERNAL):
            with recorder.span("llm.generate"):
                generator.generate("prompt")

        llm_span = next(
            span for span in exporter.get_finished_spans() if span.name == "llm.generate"
        )
        self.assertEqual(llm_span.attributes["gen_ai.response.model"], "provider-alias")

    def test_usage_metadata_falls_back_per_field(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content="SELECT 1",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 21,
                    "completion_tokens": 22,
                    "total_tokens": 43,
                }
            },
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": -1,
                "total_tokens": "invalid",
            },
        )
        recorder, exporter = create_in_memory_recorder()
        generator = LangChainSQLGenerator(model, trace_recorder=recorder)

        with recorder.query_trace(QuerySource.INTERNAL):
            with recorder.span("llm.generate"):
                generator.generate("prompt")

        llm_span = next(
            span for span in exporter.get_finished_spans() if span.name == "llm.generate"
        )
        self.assertEqual(llm_span.attributes["gen_ai.usage.input_tokens"], 10)
        self.assertEqual(llm_span.attributes["gen_ai.usage.output_tokens"], 22)
        self.assertEqual(llm_span.attributes["gen_ai.usage.total_tokens"], 43)

    def test_invalid_metadata_is_ignored_and_content_never_enters_trace(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content="SELECT sensitive_sql FROM secret_table",
            response_metadata={
                "model_name": "secret-model\nSELECT",
                "model": "prompt-model",
                "prompt": "PROMPT-CONTENT",
                "sql": "SELECT sensitive_sql",
                "raw_response": "RAW-RESPONSE-CONTENT",
                "token_usage": {
                    "prompt_tokens": True,
                    "completion_tokens": -1,
                    "total_tokens": 1.5,
                },
            },
            usage_metadata={
                "input_tokens": True,
                "output_tokens": -1,
                "total_tokens": 1.5,
            },
        )
        recorder, exporter = create_in_memory_recorder()
        generator = LangChainSQLGenerator(
            model,
            trace_recorder=recorder,
            model_name="prompt-model\nSELECT",
        )

        with recorder.query_trace(QuerySource.INTERNAL):
            with recorder.span("llm.generate"):
                self.assertEqual(
                    generator.generate("PROMPT-CONTENT"),
                    "SELECT sensitive_sql FROM secret_table",
                )

        llm_span = next(
            span for span in exporter.get_finished_spans() if span.name == "llm.generate"
        )
        self.assertEqual(
            llm_span.attributes,
            {"gen_ai.operation.name": "chat"},
        )
        rendered = repr(exporter.get_finished_spans())
        for forbidden in (
            "PROMPT-CONTENT",
            "SELECT sensitive_sql",
            "RAW-RESPONSE-CONTENT",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_missing_recorder_and_recorder_failure_are_fail_open(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="SELECT 1")
        self.assertEqual(
            LangChainSQLGenerator(model).generate("prompt"),
            "SELECT 1",
        )

        class BrokenRecorder:
            def enrich_current(self, *args, **kwargs):
                raise RuntimeError("trace-secret")

        model.invoke.return_value = SimpleNamespace(content="SELECT 2")
        generator = LangChainSQLGenerator(
            model,
            trace_recorder=BrokenRecorder(),
            model_name="test-model",
        )
        self.assertEqual(generator.generate("prompt"), "SELECT 2")
        self.assertEqual(model.invoke.call_count, 2)


if __name__ == "__main__":
    unittest.main()
