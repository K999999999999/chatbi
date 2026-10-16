"""浏览器确定性验收：真实账号 / HTTP，业务服务替身与真实 AI 验收分开。"""

import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Response
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
from src.chatbi_control.models import Base, Role, User
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess
from src.online_query.query_understanding import QueryType, ValidatedSemanticQuery
from src.query_api.app import create_app
from src.query_api.browser import BrowserSettings
from src.query_api.history_codec import encode_snapshot
from tests.history_support import BrowserHistoryRuntime, BrowserHistoryStore
from tests.operations_support import ready_operations
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
                    Decimal(120),
                    Decimal(100),
                    Decimal(-20),
                    (
                        ProductContribution(
                            "产品A",
                            Decimal(-20),
                            "continuing",
                            (FactorContribution("销量效应", Decimal(-20)),),
                        ),
                    ),
                    (
                        ProductContribution(
                            "产品A",
                            Decimal(-20),
                            "continuing",
                            (FactorContribution("销量效应", Decimal(-20)),),
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


def install_first_password_test_routes(
    app: FastAPI, sessions: sessionmaker, analyst_role_id: int
) -> None:
    """仅供隔离浏览器支持应用创建并回收首次改密测试账号。"""
    issued_accounts: dict[str, tuple[int, str]] = {}
    router = APIRouter(prefix="/__test-support/first-password-accounts")

    @router.post("", status_code=201)
    def create_account(response: Response) -> dict[str, str]:
        handle = uuid4().hex
        username = "browser-first-" + handle[:20]
        with sessions() as session:
            role = session.get(Role, analyst_role_id)
            if role is None:
                raise HTTPException(status_code=503, detail="测试角色不可用")
            user = User(
                username=username,
                password_hash=hash_password("test-password-123"),
                is_active=True,
                must_change_password=True,
                roles=[role],
            )
            session.add(user)
            session.flush()
            user_id = user.id
            session.commit()
        issued_accounts[handle] = (user_id, username)
        response.headers["X-Test-Account-Handle"] = handle
        return {"handle": handle, "username": username}

    @router.delete("/{handle}", status_code=204)
    def delete_account(handle: str) -> Response:
        account = issued_accounts.get(handle)
        if account is None:
            raise HTTPException(status_code=404, detail="测试账号不存在")
        user_id, username = account
        with sessions() as session:
            user = session.get(User, user_id)
            if user is not None:
                if user.username != username or not username.startswith(
                    "browser-first-"
                ):
                    raise HTTPException(status_code=409, detail="测试账号归属不符")
                session.delete(user)
            session.commit()
        issued_accounts.pop(handle)
        return Response(status_code=204)

    app.include_router(router)


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
        analyst_role_id = roles["analyst"].id
        for username in ("analyst", "other-user"):
            session.add(
                User(
                    username=username,
                    password_hash=hash_password("test-password-123"),
                    is_active=True,
                    must_change_password=False,
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
                "columns": ["产品", "销售额", "空值", "零", "空串"],
                "rows": [
                    [
                        '<img src="file:///etc/passwd" onerror="fetch(\'https://example.invalid/x\')"> 产品',
                        123.45,
                        None,
                        0,
                        "",
                    ],
                    *[
                        [f"产品{i:02d}-完整分类标签", (i + 1) * 10, None, 0, ""]
                        for i in range(1, 18)
                    ],
                ],
                "row_count": 18,
                "truncated": False,
                "result_metadata": {
                    "version": 1,
                    "status": "complete",
                    "columns": [
                        {
                            "index": 0,
                            "name": "产品",
                            "data_type": "string",
                            "role": "dimension",
                            "certified": True,
                            "semantic_name": "产品",
                            "definition": None,
                            "unit": None,
                            "format": "raw",
                            "reason_code": None,
                        },
                        {
                            "index": 1,
                            "name": "销售额",
                            "data_type": "number",
                            "role": "metric",
                            "certified": True,
                            "semantic_name": "人民币净销售额",
                            "definition": "净销售额定义",
                            "unit": {"key": "CNY", "label": "元"},
                            "format": "money",
                            "reason_code": None,
                        },
                        *[
                            {
                                "index": index,
                                "name": name,
                                "data_type": "unknown",
                                "role": "unknown",
                                "semantic_name": None,
                                "definition": None,
                                "unit": None,
                                "format": "raw",
                                "certified": False,
                                "reason_code": None,
                            }
                            for index, name in enumerate(("空值", "零", "空串"), 2)
                        ],
                    ],
                    "scope": {
                        "status": "complete",
                        "time_status": "unbounded",
                        "time": None,
                        "filters": [],
                        "grouping": [
                            {
                                "semantic_name": "产品",
                                "kind": "category",
                                "column_indices": [0],
                            }
                        ],
                        "warnings": [],
                    },
                    "time_axis": None,
                },
            },
            query_state=query_state(),
            source_question=question,
        )
        history_store.seed_successful_query(
            1, question, snapshot, title="浏览器导出验收历史"
        )
    app = create_app(
        BrowserQueryFixture(),
        operations=ready_operations(),
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
    install_first_password_test_routes(app, sessions, analyst_role_id)
    return app
