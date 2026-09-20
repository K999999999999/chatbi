"""基于 AuthContext 权限快照的确定性 Query RBAC。"""

from dataclasses import dataclass

from .contracts import (
    AUTHORIZED_RESOURCE,
    QUERY_ACTION,
    READ_ONLY_MODE,
    AuthContext,
    AuthorizationDecision,
    AuthorizationDecisionCode,
)


@dataclass(frozen=True, slots=True)
class RoleAuthorizationPolicyStore:
    """只允许拥有固定 query.execute 权限的本地账号查询业务资源。"""

    policy_version: str = "local-rbac-v1"
    allowed_resource: str = AUTHORIZED_RESOURCE
    allowed_action: str = QUERY_ACTION
    allowed_mode: str = READ_ONLY_MODE
    required_permission: str = "query.execute"

    def authorize(
        self,
        auth_context: AuthContext,
        *,
        resource: str,
        action: str,
        mode: str,
    ) -> AuthorizationDecision:
        if resource != self.allowed_resource:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.RESOURCE_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        if action != self.allowed_action:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.ACTION_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        if mode != self.allowed_mode:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.MODE_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        if auth_context.must_change_password:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.SUBJECT_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        if self.required_permission not in auth_context.permissions:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.SUBJECT_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        return AuthorizationDecision.allow(policy_version=self.policy_version)
