"""Query API 测试的安全身份与策略装配。"""

from collections.abc import Iterable

from src.authorization import (
    InMemoryAuditSink,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from src.query_api.app import create_app


def create_test_app(
    service: object,
    *,
    trace_recorder: object | None = None,
    subject_id: str = "analyst-1",
    allowed_subjects: Iterable[str] = ("analyst-1",),
    identity_provider: str = "test",
    audit_sink: object | None = None,
):
    """使用显式 Test Identity 创建受保护的 Query API。"""

    return create_app(
        service,
        identity_provider=StaticIdentityProviderAdapter(
            identity_provider=identity_provider,
            subject_id=subject_id,
        ),
        policy_store=StaticAuthorizationPolicyStore(
            allowed_subjects=frozenset(allowed_subjects),
            policy_version="test-policy-v1",
        ),
        audit_sink=InMemoryAuditSink() if audit_sink is None else audit_sink,
        trace_recorder=trace_recorder,
    )
