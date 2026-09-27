"""Multi-Turn Conversation Evaluation（多轮对话评测）测试。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QuerySuccess,
    ValidatedSQL,
)


class _FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.calls.append(sql)
        return QueryData(columns=("value",), rows=((1,),), truncated=False)


class _FakeConversationClient:
    def __init__(self, client_id: int, responses: dict[str, object]) -> None:
        self.client_id = client_id
        self.responses = responses
        self.calls: list[tuple[str, str | None, str]] = []

    def query(
        self,
        question: str,
        *,
        conversation_id: str | None,
        request_id: str,
    ):
        self.calls.append((question, conversation_id, request_id))
        response = self.responses[question]
        if isinstance(response, Exception):
            raise response
        return response


class MultiTurnEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset({"mart_sales.test_table"}),
            allowed_columns={"mart_sales.test_table": frozenset({"value"})},
        )
        self.reference = QueryData(columns=("value",), rows=((1,),), truncated=False)

    def test_standard_multi_turn_set_loads_and_expected_sql_passes_guard(self) -> None:
        from src.evaluation.multi_turn_evaluation import load_multi_turn_cases
        from src.online_query.context import load_query_context
        from src.online_query.sql_guard import validate_sql

        cases = load_multi_turn_cases(Path("src/evaluation/multi_turn_eval_cases.json"))
        context = load_query_context()

        self.assertEqual(len(cases), 5)
        self.assertTrue(all(case.is_valid for case in cases))
        self.assertEqual(
            {case.coverage[0] for case in cases},
            {
                "metric_replacement",
                "time_replacement",
                "dimension_append",
                "dimension_replacement",
                "failure_state_isolation",
            },
        )
        for case in cases:
            for turn in case.turns:
                if turn.expected_outcome == "result_match":
                    validate_sql(turn.expected_sql, context)

    def test_loader_requires_outcome_error_for_expected_failure_turns(self) -> None:
        from src.evaluation.multi_turn_evaluation import load_multi_turn_cases

        invalid_case = {
            "id": "MT01",
            "description": "失败轮次缺少错误码",
            "coverage": ["failure_state_isolation"],
            "turns": [
                {
                    "id": "MT01-T1",
                    "question": "第一轮",
                    "expected_sql": "SELECT t.value FROM mart_sales.test_table AS t;",
                },
                {
                    "id": "MT01-T2",
                    "question": "预期澄清",
                    "expected_outcome": "query_failure",
                },
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "multi.json"
            path.write_text(json.dumps([invalid_case]), encoding="utf-8")

            cases = load_multi_turn_cases(path)

        self.assertFalse(cases[0].is_valid)
        self.assertIn("expected_error_code", cases[0].validation_error or "")

    def test_runs_whole_conversations_in_isolated_shared_sessions(self) -> None:
        from src.evaluation.multi_turn_evaluation import (
            ConversationResponse,
            MultiTurnCase,
            MultiTurnStatus,
            MultiTurnTurn,
            run_multi_turn_evaluation,
        )

        cases = (
            MultiTurnCase(
                id="MT01",
                description="失败轮次后保留原状态",
                coverage=("failure_state_isolation",),
                turns=(
                    MultiTurnTurn(
                        id="MT01-T1",
                        question="场景一第一轮",
                        expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
                    ),
                    MultiTurnTurn(
                        id="MT01-T2",
                        question="场景一预期澄清",
                        expected_outcome="query_failure",
                        expected_error_code="CLARIFICATION_REQUIRED",
                    ),
                    MultiTurnTurn(
                        id="MT01-T3",
                        question="场景一失败后查询",
                        expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
                    ),
                ),
            ),
            MultiTurnCase(
                id="MT02",
                description="第二场景隔离",
                coverage=("metric_replacement",),
                turns=(
                    MultiTurnTurn(
                        id="MT02-T1",
                        question="场景二第一轮",
                        expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
                    ),
                    MultiTurnTurn(
                        id="MT02-T2",
                        question="场景二第二轮",
                        expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
                    ),
                ),
            ),
        )
        clients: list[_FakeConversationClient] = []

        def client_factory() -> _FakeConversationClient:
            client_id = len(clients) + 1
            conversation_id = f"conversation-{client_id}"
            responses: dict[str, object] = {
                "场景一第一轮": ConversationResponse(
                    QuerySuccess(
                        request_id="1",
                        sql="SELECT 1",
                        columns=("value",),
                        rows=((1,),),
                        row_count=1,
                        truncated=False,
                    ),
                    conversation_id,
                ),
                "场景一预期澄清": ConversationResponse(
                    QueryFailure(
                        request_id="2",
                        error_code=QueryErrorCode.CLARIFICATION_REQUIRED,
                        error_message="请补充条件",
                    ),
                    None,
                ),
                "场景一失败后查询": ConversationResponse(
                    QuerySuccess(
                        request_id="3",
                        sql="SELECT 1",
                        columns=("value",),
                        rows=((1,),),
                        row_count=1,
                        truncated=False,
                    ),
                    conversation_id,
                ),
                "场景二第一轮": ConversationResponse(
                    QuerySuccess(
                        request_id="4",
                        sql="SELECT 2",
                        columns=("value",),
                        rows=((2,),),
                        row_count=1,
                        truncated=False,
                    ),
                    conversation_id,
                ),
                "场景二第二轮": ConversationResponse(
                    QuerySuccess(
                        request_id="5",
                        sql="SELECT 1",
                        columns=("value",),
                        rows=((1,),),
                        row_count=1,
                        truncated=False,
                    ),
                    conversation_id,
                ),
            }
            client = _FakeConversationClient(client_id, responses)
            clients.append(client)
            return client

        run = run_multi_turn_evaluation(
            cases,
            client_factory,
            _FakeExecutor(),
            self.context,
        )

        self.assertEqual(
            [case.status for case in run.cases],
            [MultiTurnStatus.PASS, MultiTurnStatus.FAIL],
        )
        self.assertEqual(
            [turn.status for turn in run.cases[0].turns],
            [MultiTurnStatus.PASS, MultiTurnStatus.PASS, MultiTurnStatus.PASS],
        )
        self.assertEqual(
            [call[1] for call in clients[0].calls],
            [None, "conversation-1", "conversation-1"],
        )
        self.assertEqual(clients[1].calls[0][1], None)
        self.assertEqual(run.summary.valid_conversations, 2)
        self.assertEqual(run.summary.conversation_accuracy, 0.5)
        self.assertEqual(run.summary.execution_accuracy, 3 / 4)
        self.assertEqual(run.summary.outcome_accuracy, 1.0)

    def test_normalizes_numeric_values_serialized_as_strings_by_query_api(self) -> None:
        from src.evaluation.multi_turn_evaluation import (
            ConversationResponse,
            MultiTurnCase,
            MultiTurnStatus,
            MultiTurnTurn,
            run_multi_turn_evaluation,
        )

        turns = (
            MultiTurnTurn(
                id="MT-DECIMAL-T1",
                question="查询数值",
                expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
            ),
            MultiTurnTurn(
                id="MT-DECIMAL-T2",
                question="再查一次数值",
                expected_sql="SELECT t.value FROM mart_sales.test_table AS t;",
            ),
        )
        case = MultiTurnCase(
            id="MT-DECIMAL",
            description="Query API 将 Decimal 编码成 JSON 字符串",
            coverage=("decimal_transport",),
            turns=turns,
        )
        client = _FakeConversationClient(
            1,
            {
                "查询数值": ConversationResponse(
                    QuerySuccess(
                        request_id="1",
                        sql="SELECT 1",
                        columns=("value",),
                        rows=(("1",),),
                        row_count=1,
                        truncated=False,
                    ),
                    "conversation-1",
                ),
                "再查一次数值": ConversationResponse(
                    QuerySuccess(
                        request_id="2",
                        sql="SELECT 1",
                        columns=("value",),
                        rows=(("1",),),
                        row_count=1,
                        truncated=False,
                    ),
                    "conversation-1",
                ),
            },
        )

        run = run_multi_turn_evaluation(
            (case,),
            lambda: client,
            _FakeExecutor(),
            self.context,
        )

        self.assertEqual(run.cases[0].status, MultiTurnStatus.PASS)
        self.assertTrue(
            all(turn.status is MultiTurnStatus.PASS for turn in run.cases[0].turns)
        )


if __name__ == "__main__":
    unittest.main()
