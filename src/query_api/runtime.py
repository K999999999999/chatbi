"""HTTP Adapter 接收的启动依赖；不依赖具体资源装配实现。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.engine import Engine

from src.authorization.auth_service import AuthService
from src.authorization.contracts import (
    AuditSink,
    AuthContext,
    AuthorizationPolicyStore,
    IdentityProviderAdapter,
)
from src.authorization.query_entry import AuthorizedQueryService
from src.business_analysis.application import BusinessAnalysisSuccess
from src.observability.contracts import TraceRecorder
from src.online_query.contracts import (
    ExecutionControl,
    ExecutionProgressObserver,
    QueryFailure,
    QueryRequest,
    QueryResult,
)

from .browser import BrowserSettings


class QueryService(Protocol):
    """API Adapter 依赖的最小下游执行接口。"""

    def execute(self, request: QueryRequest) -> QueryResult:
        """执行一次已经通过授权的在线查询。"""


class AnalysisService(Protocol):
    def analyze(
        self,
        question: str,
        *,
        request_id: str,
        auth_context: AuthContext,
        analysis_run_id: str,
        progress_observer: ExecutionProgressObserver | None = None,
        execution_control: ExecutionControl | None = None,
    ) -> BusinessAnalysisSuccess | QueryFailure:
        """执行不读取普通会话的单轮经营分析。"""


class AnalysisServiceFactory(Protocol):
    def __call__(self, authorized_service: AuthorizedQueryService) -> AnalysisService:
        """使用 API 已装配的授权入口创建经营分析应用。"""


@dataclass(frozen=True)
class RuntimeDependencies:
    """一次应用启动所需的服务及边缘依赖，所有权由工厂持有。"""

    service: QueryService
    history_store: Any = None
    history_runtime: Any = None
    browser_settings: BrowserSettings | None = None
    audit_sink: AuditSink | None = None
    identity_provider: IdentityProviderAdapter | None = None
    policy_store: AuthorizationPolicyStore | None = None
    auth_service: AuthService | None = None
    trace_recorder: TraceRecorder | None = None
    query_understanding: object | None = None
    analysis_service_factory: AnalysisServiceFactory | None = None
    admin_engine: Engine | None = None
    admin_session_factory: Any = None
    admin_secret_key: str | None = field(default=None, repr=False)
