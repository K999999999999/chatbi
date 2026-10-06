"""浏览器确定性验收：真实账号 / HTTP，业务服务替身与真实 AI 验收分开。"""

import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.authorization import (
    AuthService,
    InMemoryAuditSink,
    LocalSessionIdentityProvider,
    RoleAuthorizationPolicyStore,
    hash_password,
)
from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.attribution import (
    BusinessAnalysisAttribution,
    FactorContribution,
    ProductContribution,
)
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, User
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess
from src.online_query.query_understanding import QueryType, ValidatedSemanticQuery
from src.query_api.app import create_app
from src.query_api.browser import BrowserSettings
from src.query_api.history_codec import encode_snapshot
from tests.history_support import BrowserHistoryRuntime, BrowserHistoryStore
from tests.query_api.history_fixtures import query_state
from tests.query_api.support import _DefaultRevisionAdapter


class BrowserQueryFixture:
    def certify_history_query(self, semantic):
        return query_state()

    def execute(self, request):
        if request.question == "触发澄清":
            return QueryFailure(
                request.request_id,
                QueryErrorCode.CLARIFICATION_REQUIRED,
                "请明确指标口径",
            )
        state = request.semantic_query or ValidatedSemanticQuery(
            QueryType.METRIC_ANALYSIS,
            (),
            ("人民币净销售额",),
            (),
            None,
            (),
            request.question,
        )
        rows = () if request.question == "空结果" else (("2025-02", 100, None, 0, ""),)
        return QuerySuccess(
            request.request_id,
            "SELECT 100 AS sales",
            ("月份", "销售额", "空值", "零", "空串"),
            rows,
            len(rows),
            request.question == "截断结果",
            state,
            restoration_state=query_state() if request.require_restorable else None,
        )


class BrowserAnalysisFixture:
    def analyze(
        self,
        question,
        *,
        request_id,
        auth_context,
        analysis_run_id,
        progress_observer=None,
        execution_control=None,
        report_observer=None,
    ):
        del progress_observer, report_observer
        if execution_control is not None:
            execution_control.checkpoint()
        return BusinessAnalysisSuccess(
            request_id,
            BusinessAnalysisReport(
                "两期经营分析报告",
                "按两期销售证据汇总。",
                ("数据比较已完成。",),
                "以证据结果为准。",
                ("产品变化贡献已核验。",),
                ("检查主要产品。",),
                ("current-overall",),
                (),
                BusinessAnalysisAttribution(
                    "人民币毛利",
                    "2025年2月",
                    "2025年1月",
                    Decimal("120"),
                    Decimal("100"),
                    Decimal("-20"),
                    (
                        ProductContribution(
                            "产品A",
                            Decimal("-20"),
                            "continuing",
                            (FactorContribution("销量效应", Decimal("-20")),),
                        ),
                    ),
                    (
                        ProductContribution(
                            "产品A",
                            Decimal("-20"),
                            "continuing",
                            (FactorContribution("销量效应", Decimal("-20")),),
                        ),
                    ),
                ),
            ),
            (
                TaskResult(
                    "current-overall",
                    TaskStatus.COMPLETED,
                    ("人民币毛利",),
                    ((100,),),
                    1,
                ),
            ),
            analysis_run_id,
        )


class BrowserRevisionAdapter(_DefaultRevisionAdapter):
    def understand_history_revision(self, previous, question):
        return self.understand_revision(previous, question), {
            field: ("keep", None)
            for field in ("order_by", "row_limit", "aggregate_filters", "selection")
        }


def create_browser_app():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        roles = seed_rbac(session)
        for username, first in (
            ("analyst", False),
            ("other-user", False),
            ("new-user", True),
        ):
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("test-password-123"),
                    is_active=True,
                    must_change_password=first,
                    roles=[roles["analyst"]],
                )
            )
        session.commit()
    auth = AuthService(sessions)
    directory = Path(__file__).resolve().parents[1] / "frontend/dist"
    history_store = BrowserHistoryStore()
    if os.getenv("CHATBI_RESULT_EXPORT_BROWSER_TEST") == "1":
        question = "导出测试快照问题"
        snapshot = encode_snapshot(
            "query",
            {
                "request_id": "browser-export-request",
                "sql": "SELECT 1",
                "columns": ["月份", "销售额", "空值", "零", "空串"],
                "rows": [["2026-02", 123.45, None, 0, ""]],
                "row_count": 1,
                "truncated": False,
                "result_metadata": None,
            },
            query_state=query_state(),
            source_question=question,
        )
        history_store.seed_successful_query(
            1, question, snapshot, title="浏览器导出验收历史"
        )
    return create_app(
        BrowserQueryFixture(),
        analysis_service=BrowserAnalysisFixture(),
        auth_service=auth,
        audit_sink=InMemoryAuditSink(),
        identity_provider=LocalSessionIdentityProvider(auth),
        policy_store=RoleAuthorizationPolicyStore(),
        query_understanding=BrowserRevisionAdapter(),
        history_store=history_store,
        history_runtime=BrowserHistoryRuntime(history_store),
        browser_settings=BrowserSettings(
            os.getenv("CHATBI_BROWSER_TEST_ORIGIN", "http://127.0.0.1:18001"),
            False,
            directory,
        ),
    )
