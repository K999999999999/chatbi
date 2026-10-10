"""只读运行状态HTTP入口，复用身份/浏览器边界且不延长Session。"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.authorization.contracts import (
    AuthenticationRequired,
    IdentityProviderUnavailable,
)

from .browser import COOKIE_NAME, BrowserIdentityProvider, reject_browser_request
from .operations import OperationsState


def mount_operations_api(app):
    def snapshot():
        state = getattr(app.state, "operations", None)
        return state if state is not None else OperationsState()

    @app.get("/ready")
    def ready():
        result = snapshot().snapshot()
        return JSONResponse(
            result,
            status_code=200 if result["status"] == "ready" else 503,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/operations/status")
    def status(request: Request):
        if request.cookies.get(COOKIE_NAME):
            reject_browser_request(request, app.state.browser_settings, write=False)
        provider = app.state.identity_provider
        # 状态不能使用worker兼容fallback；只读能力缺失时拒绝认证。
        if isinstance(provider, BrowserIdentityProvider) and not request.cookies.get(
            COOKIE_NAME
        ):
            provider = provider.bearer_provider
        authenticate = getattr(provider, "authenticate_readonly", None)
        if not callable(authenticate):
            if not request.cookies.get(COOKIE_NAME) and not request.headers.get(
                "authorization"
            ):
                raise HTTPException(401, "请先登录")
            raise HTTPException(503, "只读身份认证暂时不可用")
        try:
            context = authenticate(request)
        except AuthenticationRequired:
            raise HTTPException(401, "登录已失效，请重新登录") from None
        except IdentityProviderUnavailable:
            raise HTTPException(503, "身份认证服务暂时不可用") from None
        detailed = (
            not context.must_change_password and "admin.audit" in context.permissions
        )
        result = snapshot().snapshot(detailed=detailed)
        result.update(
            version=1,
            query_available=result["status"] == "ready",
            message="" if result["status"] == "ready" else "服务暂时不可用，请稍后重试",
        )
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
