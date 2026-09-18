"""企业身份与数据授权 V1 的 Application-level Contract 测试。"""

from dataclasses import FrozenInstanceError
from unittest import TestCase
from unittest.mock import Mock

from src.authorization import AuditDecision, InMemoryAuditSink
from src.authorization.contracts import (
    AuthContext,
    AuthorizationDecision,
    AuthorizationDecisionCode,
    AuthorizationPolicyUnavailable,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from src.authorization.query_entry import AuthorizedQueryService
from src.online_query.contracts import QueryErrorCode, QueryRequest, QuerySuccess


class AuthorizationCoreTest(TestCase):
    def setUp(self) -> None:
        self.query_service = Mock()
        self.query_service.execute.return_value = QuerySuccess(
            request_id="req-1",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
        )
        self.policy = StaticAuthorizationPolicyStore(
            allowed_subjects=frozenset({"analyst-1"}),
            policy_version="policy-v1",
        )
        self.audit_sink = InMemoryAuditSink()
        self.authorized = AuthContext(
            subject_id="analyst-1",
            identity_provider="test",
        )

    def _service(self, policy=None, *, audit_sink=None, **kwargs):
        return AuthorizedQueryService(
            self.query_service,
            self.policy if policy is None else policy,
            audit_sink=self.audit_sink if audit_sink is None else audit_sink,
            **kwargs,
        )

    def test_authorized_context_reaches_query_service(self) -> None:
        service = self._service()

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-1"),
            auth_context=self.authorized,
        )

        self.assertIsInstance(result, QuerySuccess)
        self.query_service.execute.assert_called_once()

    def test_authorized_query_emits_complete_allow_audit_event(self) -> None:
        service = self._service()

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-allow"),
            auth_context=self.authorized,
        )

        self.assertIsInstance(result, QuerySuccess)
        self.assertEqual(len(self.audit_sink.events), 1)
        event = self.audit_sink.events[0]
        self.assertEqual(event.request_id, "req-allow")
        self.assertEqual(event.subject_id, "analyst-1")
        self.assertEqual(event.identity_provider, "test")
        self.assertEqual(event.resource, "mart_sales")
        self.assertEqual(event.action, "query")
        self.assertEqual(event.decision, AuditDecision.ALLOW)
        self.assertEqual(event.reason_code, "AUTHORIZED")
        self.assertEqual(event.policy_version, "policy-v1")
        self.assertIsNotNone(event.timestamp.tzinfo)
        record = event.to_record()
        self.assertEqual(
            set(record),
            {
                "request_id",
                "subject_id",
                "identity_provider",
                "resource",
                "action",
                "decision",
                "reason_code",
                "policy_version",
                "timestamp",
            },
        )
        self.assertNotIn("查询销售额", record.values())
        self.assertNotIn("SELECT 1", record.values())

    def test_unauthorized_query_emits_deny_audit_event(self) -> None:
        service = self._service()
        unauthorized = AuthContext(subject_id="unknown-user", identity_provider="test")

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-deny"),
            auth_context=unauthorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHORIZATION_DENIED,
        )
        self.assertEqual(len(self.audit_sink.events), 1)
        event = self.audit_sink.events[0]
        self.assertEqual(event.request_id, "req-deny")
        self.assertEqual(event.decision, AuditDecision.DENY)
        self.assertEqual(event.reason_code, "SUBJECT_NOT_ALLOWED")
        self.assertEqual(event.policy_version, "policy-v1")
        self.query_service.query.assert_not_called()

    def test_bound_entry_reuses_authorization_with_explicit_context(self) -> None:
        service = self._service()
        entry = service.bind(self.authorized)

        result = entry.query(
            QueryRequest(question="查询销售额", request_id="req-bound")
        )

        self.assertIsInstance(result, QuerySuccess)
        self.query_service.execute.assert_called_once_with(
            QueryRequest(question="查询销售额", request_id="req-bound")
        )

    def test_missing_context_returns_authentication_required_before_query(self) -> None:
        service = self._service()

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-no-auth"),
            auth_context=None,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_REQUIRED,
        )
        self.assertEqual(len(self.audit_sink.events), 1)
        event = self.audit_sink.events[0]
        self.assertEqual(event.decision, AuditDecision.DENY)
        self.assertEqual(event.reason_code, "AUTH_CONTEXT_MISSING")
        self.assertEqual(event.subject_id, "anonymous")
        self.assertEqual(event.identity_provider, "unknown")
        self.assertEqual(event.policy_version, "unavailable")
        self.query_service.query.assert_not_called()

    def test_unknown_subject_is_denied_before_query(self) -> None:
        service = self._service()
        unauthorized = AuthContext(
            subject_id="unknown-user",
            identity_provider="test",
        )

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-deny"),
            auth_context=unauthorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHORIZATION_DENIED,
        )
        self.query_service.query.assert_not_called()

    def test_unsupported_resource_is_denied_before_query(self) -> None:
        service = self._service(
            resource="other_schema",
        )

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-scope"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHORIZATION_DENIED,
        )
        self.query_service.query.assert_not_called()

    def test_unsupported_action_and_mode_are_denied_before_query(self) -> None:
        for kwargs in (
            {"action": "write"},
            {"mode": "read_write"},
        ):
            with self.subTest(kwargs=kwargs):
                service = self._service(
                    **kwargs,
                )

                result = service.query(
                    QueryRequest(question="查询销售额", request_id="req-scope"),
                    auth_context=self.authorized,
                )

                self.assertEqual(
                    getattr(result, "error_code", None),
                    QueryErrorCode.AUTHORIZATION_DENIED,
                )
                self.query_service.query.assert_not_called()

    def test_policy_unavailable_returns_controlled_authentication_error(self) -> None:
        policy = Mock()
        policy.authorize.side_effect = AuthorizationPolicyUnavailable(
            "policy store unavailable"
        )
        service = self._service(policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-policy-error"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
        )
        self.assertEqual(len(self.audit_sink.events), 1)
        self.assertEqual(
            self.audit_sink.events[0].reason_code,
            "POLICY_STORE_UNAVAILABLE",
        )
        self.query_service.query.assert_not_called()

    def test_invalid_policy_decision_fails_closed_before_query(self) -> None:
        policy = Mock()
        policy.authorize.return_value = object()
        service = self._service(policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-invalid-policy"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
        )
        self.query_service.query.assert_not_called()

    def test_audit_sink_failure_fails_closed_before_query(self) -> None:
        audit_sink = Mock()
        audit_sink.emit.side_effect = RuntimeError("audit sink unavailable")
        service = self._service(audit_sink=audit_sink)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-audit-error"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
        )
        self.assertEqual(
            getattr(result, "internal_reason", None),
            "AUDIT_SINK_UNAVAILABLE",
        )
        self.query_service.query.assert_not_called()

    def test_missing_audit_sink_fails_closed_before_query(self) -> None:
        service = AuthorizedQueryService(self.query_service, self.policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-no-audit"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
        )
        self.assertEqual(
            getattr(result, "internal_reason", None),
            "AUDIT_SINK_UNAVAILABLE",
        )
        self.query_service.query.assert_not_called()

    def test_static_identity_provider_returns_canonical_context(self) -> None:
        adapter = StaticIdentityProviderAdapter(
            identity_provider="test",
            subject_id="analyst-1",
        )

        context = adapter.authenticate()

        self.assertEqual(
            context,
            AuthContext(subject_id="analyst-1", identity_provider="test"),
        )

    def test_auth_context_rejects_empty_identity_values(self) -> None:
        with self.assertRaises(ValueError):
            AuthContext(subject_id="", identity_provider="test")
        with self.assertRaises(ValueError):
            AuthContext(subject_id="analyst-1", identity_provider="")

    def test_authorization_decision_is_immutable_and_explicit(self) -> None:
        decision = AuthorizationDecision.allow(policy_version="policy-v1")

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, "AUTHORIZED")
        self.assertEqual(decision.policy_version, "policy-v1")
        self.assertEqual(decision.reason_code, AuthorizationDecisionCode.ALLOWED.value)
        with self.assertRaises(FrozenInstanceError):
            decision.allowed = False  # type: ignore[misc]


if __name__ == "__main__":
    import unittest

    unittest.main()
