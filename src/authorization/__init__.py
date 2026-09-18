"""ChatBI 身份与数据授权核心。"""

from .contracts import (
    AuthContext,
    AuthenticationRequired,
    AuthorizationDecision,
    AuthorizationDecisionCode,
    AuthorizationPolicyStore,
    AuthorizationPolicyUnavailable,
    IdentityProviderAdapter,
    IdentityProviderUnavailable,
    StaticAuthorizationPolicyStore,
    StaticIdentityProviderAdapter,
)
from .query_entry import AuthorizedQueryService, authorization_failure

__all__ = [
    "AuthContext",
    "AuthenticationRequired",
    "AuthorizationDecision",
    "AuthorizationDecisionCode",
    "AuthorizationPolicyStore",
    "AuthorizationPolicyUnavailable",
    "AuthorizedQueryService",
    "IdentityProviderUnavailable",
    "IdentityProviderAdapter",
    "StaticAuthorizationPolicyStore",
    "StaticIdentityProviderAdapter",
    "authorization_failure",
]
