"""Trace Core、生命周期和安全降级的独立确定性测试。"""

from contextlib import redirect_stderr, redirect_stdout
import io
import re
import unittest
from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult

from src.observability.config import ObservabilityConfig
from src.observability.contracts import (
    ErrorType,
    QuerySource,
    TraceOutcome,
)
from src.observability import tracing
from src.observability.tracing import (
    SafeTraceRecorder,
    create_in_memory_recorder,
    create_trace_recorder,
)


TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ObservabilityTracingTest(unittest.TestCase):
    def test_root_child_and_borrowed_scope_have_one_root_and_root_ends_last(self) -> None:
        recorder, exporter = create_in_memory_recorder()

        with recorder.query_trace(
            QuerySource.INTERNAL,
            attributes={"chatbi.request.id": "req-1"},
        ) as root:
            self.assertTrue(root.owns_root)
            self.assertRegex(root.trace_id, TRACE_ID_RE)
            self.assertNotEqual(int(root.trace_id, 16), 0)

            with recorder.span("child", {"chatbi.test": "value"}) as child:
                self.assertEqual(child.trace_id, root.trace_id)
                self.assertEqual(
                    trace.get_current_span().get_span_context().trace_id,
                    int(root.trace_id, 16),
                )

            with recorder.query_trace(QuerySource.EVALUATION) as borrowed:
                self.assertFalse(borrowed.owns_root)
                self.assertEqual(borrowed.trace_id, root.trace_id)

        self.assertIsNone(tracing._ACTIVE_ROOT.get())

        spans = exporter.get_finished_spans()
        self.assertEqual([span.name for span in spans], ["child", "query.request"])
        self.assertEqual(sum(span.name == "query.request" for span in spans), 1)
        self.assertEqual(
            spans[-1].attributes["chatbi.request.source"],
            QuerySource.INTERNAL.value,
        )

    def test_root_context_is_cleaned_and_next_trace_does_not_borrow(self) -> None:
        recorder, exporter = create_in_memory_recorder()

        with recorder.query_trace(QuerySource.INTERNAL) as first:
            first_id = first.trace_id
        with recorder.query_trace(QuerySource.INTERNAL) as second:
            self.assertTrue(second.owns_root)
            self.assertNotEqual(second.trace_id, first_id)

        spans = exporter.get_finished_spans()
        roots = [span for span in spans if span.name == "query.request"]
        self.assertEqual(len(roots), 2)
        self.assertNotEqual(roots[0].context.trace_id, roots[1].context.trace_id)

    def test_always_off_still_generates_valid_nonzero_trace_id(self) -> None:
        recorder = create_trace_recorder(ObservabilityConfig(enabled=False))

        with recorder.query_trace(QuerySource.INTERNAL) as root:
            self.assertRegex(root.trace_id, TRACE_ID_RE)
            self.assertNotEqual(int(root.trace_id, 16), 0)
            self.assertFalse(trace.get_current_span().is_recording())
            with recorder.span("child") as child:
                self.assertEqual(child.trace_id, root.trace_id)

    def test_exception_is_not_recorded_and_safe_fields_do_not_leak(self) -> None:
        recorder, exporter = create_in_memory_recorder()

        try:
            with recorder.query_trace(QuerySource.INTERNAL):
                with recorder.span("failing"):
                    raise ValueError("raw-secret-exception")
        except ValueError:
            pass

        with recorder.query_trace(QuerySource.INTERNAL):
            recorder.enrich_current(
                {
                    "chatbi.secret": "raw-secret-value",
                    "chatbi.status": "ok",
                    "component": "raw-secret-value",
                },
                outcome=TraceOutcome.TECHNICAL_FAILURE,
                error_type=ErrorType.DATABASE,
                error_code="DATABASE_ERROR",
            )

        spans = exporter.get_finished_spans()
        failing = next(span for span in spans if span.name == "failing")
        self.assertEqual(failing.events, ())
        self.assertIsNone(failing.status.description)
        enriched = [span for span in spans if span.name == "query.request"][-1]
        self.assertNotIn("chatbi.secret", enriched.attributes)
        self.assertEqual(enriched.attributes["chatbi.status"], "ok")
        self.assertNotIn("component", enriched.attributes)
        self.assertEqual(enriched.attributes["chatbi.error.type"], "DATABASE")
        self.assertNotIn("raw-secret", repr(spans))

    def test_safe_wrapper_and_faulty_exporter_are_no_throw(self) -> None:
        class BrokenRecorder:
            def query_trace(self, *args, **kwargs):
                raise RuntimeError("export-secret")

            def span(self, *args, **kwargs):
                raise RuntimeError("span-secret")

            def enrich_current(self, *args, **kwargs):
                raise RuntimeError("enrich-secret")

        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            safe = SafeTraceRecorder(BrokenRecorder())
            with safe.query_trace(QuerySource.INTERNAL) as root:
                self.assertRegex(root.trace_id, TRACE_ID_RE)
                with safe.query_trace(QuerySource.INTERNAL) as borrowed:
                    self.assertFalse(borrowed.owns_root)
                    self.assertEqual(borrowed.trace_id, root.trace_id)
            self.assertIsNone(tracing._ACTIVE_ROOT.get())
            with safe.query_trace(QuerySource.INTERNAL) as next_root:
                self.assertTrue(next_root.owns_root)
                self.assertNotEqual(next_root.trace_id, root.trace_id)
            with safe.span("child"):
                pass
            safe.enrich_current(error_code="RAW SECRET")
        self.assertNotIn("export-secret", output.getvalue())
        self.assertNotIn("span-secret", output.getvalue())
        self.assertNotIn("enrich-secret", output.getvalue())

        with patch.object(
            tracing,
            "OTLPSpanExporter",
            side_effect=RuntimeError("endpoint-secret"),
        ):
            recorder = create_trace_recorder(
                ObservabilityConfig(
                    enabled=True,
                    otlp_traces_endpoint="http://collector/v1/traces",
                )
            )
            with recorder.query_trace(QuerySource.INTERNAL) as root:
                self.assertRegex(root.trace_id, TRACE_ID_RE)

    def test_start_span_failure_uses_noop_root_context_and_cleans_it(self) -> None:
        class BrokenTracer:
            def start_span(self, *args, **kwargs):
                raise TimeoutError("provider-raw-secret")

        class Provider:
            def get_tracer(self, name):
                return BrokenTracer()

            def shutdown(self):
                return None

        recorder = SafeTraceRecorder(tracing.OtelTraceRecorder(Provider()))
        with recorder.query_trace(QuerySource.INTERNAL) as root:
            self.assertTrue(root.owns_root)
            with recorder.query_trace(QuerySource.INTERNAL) as borrowed:
                self.assertFalse(borrowed.owns_root)
                self.assertEqual(borrowed.trace_id, root.trace_id)
            self.assertEqual(tracing._current_trace_id(), root.trace_id)
        self.assertIsNone(tracing._ACTIVE_ROOT.get())
        with recorder.query_trace(QuerySource.INTERNAL) as next_root:
            self.assertTrue(next_root.owns_root)
            self.assertNotEqual(next_root.trace_id, root.trace_id)

    def test_root_content_capture_attribute_is_configured_and_cannot_be_overridden(self) -> None:
        recorder, exporter = create_in_memory_recorder(
            ObservabilityConfig(
                runtime_env="local",
                content_capture_enabled=True,
            )
        )

        with recorder.query_trace(
            QuerySource.INTERNAL,
            attributes={"chatbi.content_capture.enabled": False},
        ):
            pass

        root = exporter.get_finished_spans()[0]
        self.assertTrue(root.attributes["chatbi.content_capture.enabled"])

    def test_root_content_capture_attribute_cannot_be_changed_by_enrich(self) -> None:
        for configured, attempted in ((True, False), (False, True)):
            with self.subTest(configured=configured, attempted=attempted):
                recorder, exporter = create_in_memory_recorder(
                    ObservabilityConfig(
                        runtime_env="local",
                        content_capture_enabled=configured,
                    )
                )

                with recorder.query_trace(QuerySource.INTERNAL):
                    recorder.enrich_current(
                        {"chatbi.content_capture.enabled": attempted}
                    )

                root = exporter.get_finished_spans()[0]
                self.assertEqual(
                    root.attributes["chatbi.content_capture.enabled"],
                    configured,
                )

    def test_unknown_chatbi_attributes_are_rejected_and_safe_values_are_kept(self) -> None:
        recorder, exporter = create_in_memory_recorder()

        with recorder.query_trace(QuerySource.INTERNAL):
            recorder.enrich_current(
                {
                    "chatbi.unknown": "raw-secret-value",
                    "chatbi.request.id": "request-1",
                    "chatbi.sql.sha256": "a" * 64,
                    "chatbi.result.row_count": 3,
                    "chatbi.result.status": "SUCCESS",
                }
            )

        root = exporter.get_finished_spans()[0]
        self.assertNotIn("chatbi.unknown", root.attributes)
        self.assertEqual(root.attributes["chatbi.request.id"], "request-1")
        self.assertEqual(root.attributes["chatbi.sql.sha256"], "a" * 64)
        self.assertEqual(root.attributes["chatbi.result.row_count"], 3)
        self.assertEqual(root.attributes["chatbi.result.status"], "SUCCESS")
        self.assertNotIn("raw-secret", repr(root.attributes))

    def test_batch_exporter_failures_are_safe_and_query_does_not_force_flush(self) -> None:
        class FailingExporter:
            def __init__(self, **kwargs):
                del kwargs

            def export(self, spans):
                del spans
                raise TimeoutError("export-raw-secret")

            def shutdown(self):
                raise RuntimeError("shutdown-raw-secret")

        config = ObservabilityConfig(
            enabled=True,
            otlp_traces_endpoint="http://collector/v1/traces",
        )
        with patch.object(tracing, "OTLPSpanExporter", FailingExporter):
            recorder = create_trace_recorder(config)

        provider = recorder._delegate._provider
        processors = provider._active_span_processor._span_processors
        self.assertEqual(len(processors), 1)
        self.assertIsInstance(processors[0], BatchSpanProcessor)
        with patch.object(provider, "force_flush", wraps=provider.force_flush) as force_flush:
            with self.assertLogs(tracing._LOGGER, level="WARNING") as logs:
                with recorder.query_trace(QuerySource.INTERNAL):
                    pass
                self.assertFalse(force_flush.called)
                self.assertTrue(provider.force_flush())
                recorder.shutdown()

        output = "\n".join(logs.output)
        self.assertNotIn("export-raw-secret", output)
        self.assertNotIn("shutdown-raw-secret", output)
        self.assertNotIn("Traceback", output)
        self.assertIn("stage=exporter_export", output)
        self.assertIn("stage=exporter_shutdown", output)

    def test_safe_exporter_returns_failure_without_propagating_exporter_exception(self) -> None:
        class BrokenExporter:
            def export(self, spans):
                raise RuntimeError("secret-export")

            def shutdown(self):
                raise RuntimeError("secret-shutdown")

        exporter = tracing._SafeExporter(BrokenExporter())
        with self.assertLogs(tracing._LOGGER, level="WARNING") as logs:
            self.assertEqual(exporter.export(()), SpanExportResult.FAILURE)
            exporter.shutdown()
        output = "\n".join(logs.output)
        self.assertNotIn("secret-export", output)
        self.assertNotIn("secret-shutdown", output)
        self.assertNotIn("Traceback", output)

    def test_otlp_http_exporter_receives_timeout_in_seconds(self) -> None:
        captured: dict[str, object] = {}

        class FakeExporter:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def export(self, spans):
                return None

            def shutdown(self):
                return None

        with patch.object(tracing, "OTLPSpanExporter", FakeExporter):
            recorder = create_trace_recorder(
                ObservabilityConfig(
                    enabled=True,
                    otlp_traces_endpoint="http://collector/v1/traces",
                    otlp_timeout_seconds=2.5,
                    otlp_headers={"Authorization": "Bearer secret"},
                )
            )

        self.assertEqual(captured["endpoint"], "http://collector/v1/traces")
        self.assertEqual(captured["timeout"], 2.5)
        self.assertEqual(captured["headers"], {"Authorization": "Bearer secret"})
        recorder.shutdown()


if __name__ == "__main__":
    unittest.main()
