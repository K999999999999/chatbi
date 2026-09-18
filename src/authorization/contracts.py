"""身份与数据授权的稳定 Contract。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

AUTHORIZED_RESOURCE = "mart_sales"
QUERY_ACTION = "query"
READ_ONLY_MODE = "read_only"


class AuthorizationDecisionCode(StrEnum):
    """静态授权策略返回的确定性原因码。"""

    ALLOWED = "AUTHORIZED"
    SUBJECT_NOT_ALLOWED = "SUBJECT_NOT_ALLOWED"
    RESOURCE_NOT_ALLOWED = "RESOURCE_NOT_ALLOWED"
    ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"
    MODE_NOT_ALLOWED = "MODE_NOT_ALLOWED"


@dataclass(frozen=True, slots=True)
class AuthContext:
    """已经由服务端 Provider Adapter 规范化的身份。"""

    subject_id: str
    identity_provider: str

    def __post_init__(self) -> None:
        if not isinstance(self.subject_id, str) or not self.subject_id.strip():
            raise ValueError("subject_id 必须是非空字符串")
        if (
            not isinstance(self.identity_provider, str)
            or not self.identity_provider.strip()
        ):
            raise ValueError("identity_provider 必须是非空字符串")
        object.__setattr__(self, "subject_id", self.subject_id.strip())
        object.__setattr__(
            self,
            "identity_provider",
            self.identity_provider.strip(),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """一次确定性的资源授权决策。"""

    allowed: bool
    reason_code: str
    policy_version: str

    @classmethod
    def allow(cls, *, policy_version: str) -> "AuthorizationDecision":
        return cls(
            allowed=True,
            reason_code=AuthorizationDecisionCode.ALLOWED.value,
            policy_version=policy_version,
        )

    @classmethod
    def deny(
        cls,
        *,
        reason_code: AuthorizationDecisionCode,
        policy_version: str,
    ) -> "AuthorizationDecision":
        return cls(
            allowed=False,
            reason_code=reason_code.value,
            policy_version=policy_version,
        )


class AuthorizationPolicyUnavailable(RuntimeError):
    """授权策略暂时不可用，调用方必须 Fail Closed。"""


class AuthenticationRequired(RuntimeError):
    """请求没有可用的经过验证的身份。"""


class IdentityProviderUnavailable(RuntimeError):
    """身份 Provider 暂时不可用，调用方必须 Fail Closed。"""


class AuthorizationPolicyStore(Protocol):
    """Application Service 使用的最小授权策略接口。"""

    def authorize(
        self,
        auth_context: AuthContext,
        *,
        resource: str,
        action: str,
        mode: str,
    ) -> AuthorizationDecision:
        """返回一次确定性的授权决策。"""


class IdentityProviderAdapter(Protocol):
    """将边缘身份输入转换为可信 AuthContext 的 Provider 接口。"""

    @property
    def identity_provider(self) -> str:
        """返回 Provider 的稳定名称。"""

    def authenticate(self, provider_input: object | None = None) -> AuthContext:
        """验证 Provider 输入并返回规范化身份。"""


@dataclass(frozen=True, slots=True)
class StaticAuthorizationPolicyStore:
    """V1 使用的内存静态白名单策略。"""

    allowed_subjects: frozenset[str]
    policy_version: str
    allowed_resource: str = AUTHORIZED_RESOURCE
    allowed_action: str = QUERY_ACTION
    allowed_mode: str = READ_ONLY_MODE

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("policy_version 必须是非空字符串")
        if not isinstance(self.allowed_subjects, frozenset):
            object.__setattr__(
                self,
                "allowed_subjects",
                frozenset(self.allowed_subjects),
            )

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
        if auth_context.subject_id not in self.allowed_subjects:
            return AuthorizationDecision.deny(
                reason_code=AuthorizationDecisionCode.SUBJECT_NOT_ALLOWED,
                policy_version=self.policy_version,
            )
        return AuthorizationDecision.allow(policy_version=self.policy_version)


@dataclass(frozen=True, slots=True)
class StaticIdentityProviderAdapter:
    """供 Demo/Test 环境使用的服务端静态身份 Adapter。"""

    identity_provider: str
    subject_id: str

    def __post_init__(self) -> None:
        AuthContext(
            subject_id=self.subject_id,
            identity_provider=self.identity_provider,
        )

    def authenticate(self, provider_input: object | None = None) -> AuthContext:
        del provider_input
        return AuthContext(
            subject_id=self.subject_id,
            identity_provider=self.identity_provider,
        )
