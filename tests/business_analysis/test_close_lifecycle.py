"""清理失败仍必须释放剩余经营分析资源。"""

from unittest.mock import Mock

from langgraph.checkpoint.memory import InMemorySaver

from src.business_analysis.application import BusinessAnalysisApplication


def test_analysis_close_continues_after_store_failure_and_is_idempotent():
    store = Mock()
    store.close.side_effect = RuntimeError("test cleanup failed")
    pool = Mock()
    checkpointer = InMemorySaver()
    checkpointer.conn = pool
    application = BusinessAnalysisApplication(
        Mock(),
        decomposer=Mock(),
        summarizer=Mock(),
        context_provider=Mock(),
        checkpointer=checkpointer,
        run_store=store,
    )
    application.close()
    application.close()
    store.close.assert_called_once()
    pool.close.assert_called_once()
