"""浏览器确定性验收：真实账号 / HTTP，业务服务替身与真实 AI 验收分开。"""

import os
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
from src.chatbi_control.bootstrap import seed_rbac
from src.chatbi_control.models import Base, User
from src.online_query.contracts import QueryErrorCode, QueryFailure, QuerySuccess
from src.online_query.query_understanding import QueryType, ValidatedSemanticQuery
from src.query_api.app import create_app
from src.query_api.browser import BrowserSettings
from tests.query_api.support import _DefaultRevisionAdapter


class BrowserQueryFixture:
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
        )


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
    return create_app(
        BrowserQueryFixture(),
        auth_service=auth,
        audit_sink=InMemoryAuditSink(),
        identity_provider=LocalSessionIdentityProvider(auth),
        policy_store=RoleAuthorizationPolicyStore(),
        query_understanding=_DefaultRevisionAdapter(),
        browser_settings=BrowserSettings(
            os.getenv("CHATBI_BROWSER_TEST_ORIGIN", "http://127.0.0.1:18001"),
            False,
            directory,
        ),
    )
