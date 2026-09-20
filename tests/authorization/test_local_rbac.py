"""本地 Session Provider 和固定 Query RBAC 测试。"""

from unittest import TestCase
from unittest.mock import Mock

from src.authorization import (
    AuthContext,
    AuthenticationRequired,
    LocalSessionIdentityProvider,
    RoleAuthorizationPolicyStore,
)
from src.authorization.auth_service import SessionExpired


class LocalRbacTest(TestCase):
    def test_query_permission_and_first_password_change_are_deterministic(self) -> None:
        policy = RoleAuthorizationPolicyStore()
        allowed = AuthContext(
            subject_id="analyst-1",
            identity_provider="local",
            permissions=frozenset({"query.execute"}),
        )
        first_login = AuthContext(
            subject_id="analyst-1",
            identity_provider="local",
            permissions=frozenset({"query.execute"}),
            must_change_password=True,
        )
        no_permission = AuthContext(
            subject_id="admin-1",
            identity_provider="local",
            permissions=frozenset(),
        )

        self.assertTrue(
            policy.authorize(
                allowed,
                resource="mart_sales",
                action="query",
                mode="read_only",
            ).allowed
        )
        self.assertFalse(
            policy.authorize(
                first_login,
                resource="mart_sales",
                action="query",
                mode="read_only",
            ).allowed
        )
        self.assertFalse(
            policy.authorize(
                no_permission,
                resource="mart_sales",
                action="query",
                mode="read_only",
            ).allowed
        )

    def test_local_provider_reads_bearer_session_and_fails_closed(self) -> None:
        service = Mock()
        context = AuthContext(
            subject_id="analyst-1",
            identity_provider="local",
            permissions=frozenset({"query.execute"}),
        )
        service.authenticate_session.return_value = context
        provider = LocalSessionIdentityProvider(service)

        request = Mock()
        request.headers.get.return_value = "Bearer token-1"
        self.assertEqual(provider.authenticate(request), context)
        service.authenticate_session.assert_called_once_with("token-1")

        request.headers.get.return_value = ""
        with self.assertRaises(AuthenticationRequired):
            provider.authenticate(request)

        service.authenticate_session.side_effect = SessionExpired("expired")
        request.headers.get.return_value = "Bearer token-2"
        with self.assertRaises(AuthenticationRequired):
            provider.authenticate(request)
