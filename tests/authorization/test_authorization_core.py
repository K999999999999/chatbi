"""企业身份与数据授权 V1 的 Application-level Contract 测试。"""

from dataclasses import FrozenInstanceError
from unittest import TestCase
from unittest.mock import Mock

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
        self.query_service.query.return_value = QuerySuccess(
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
        self.authorized = AuthContext(
            subject_id="analyst-1",
            identity_provider="test",
        )

    def test_authorized_context_reaches_query_service(self) -> None:
        service = AuthorizedQueryService(self.query_service, self.policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-1"),
            auth_context=self.authorized,
        )

        self.assertIsInstance(result, QuerySuccess)
        self.query_service.query.assert_called_once()

    def test_missing_context_returns_authentication_required_before_query(self) -> None:
        service = AuthorizedQueryService(self.query_service, self.policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-no-auth"),
            auth_context=None,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_REQUIRED,
        )
        self.query_service.query.assert_not_called()

    def test_unknown_subject_is_denied_before_query(self) -> None:
        service = AuthorizedQueryService(self.query_service, self.policy)
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
        service = AuthorizedQueryService(
            self.query_service,
            self.policy,
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
                service = AuthorizedQueryService(
                    self.query_service,
                    self.policy,
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
        service = AuthorizedQueryService(self.query_service, policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-policy-error"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
        )
        self.query_service.query.assert_not_called()

    def test_invalid_policy_decision_fails_closed_before_query(self) -> None:
        policy = Mock()
        policy.authorize.return_value = object()
        service = AuthorizedQueryService(self.query_service, policy)

        result = service.query(
            QueryRequest(question="查询销售额", request_id="req-invalid-policy"),
            auth_context=self.authorized,
        )

        self.assertEqual(
            getattr(result, "error_code", None),
            QueryErrorCode.AUTHENTICATION_UNAVAILABLE,
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
