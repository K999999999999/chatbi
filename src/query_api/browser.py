"""浏览器 HTTP 身份、来源门禁与静态网页边界。"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictStr

from src.authorization.auth_service import AuthenticationFailed, SessionExpired
from src.authorization.contracts import (
    AuthenticationRequired,
    IdentityProviderUnavailable,
)

COOKIE_NAME = "chatbi_web_session"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserSettings:
    origin: str
    secure: bool = True
    dist_dir: Path | None = None

    def __post_init__(self):
        parsed = urlsplit(self.origin)
        if (
            any(char.isspace() or ord(char) < 32 for char in self.origin)
            or parsed.port == 0
        ):
            raise ValueError("CHATBI_WEB_ORIGIN 包含非法主机或端口")
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in self.origin
        ):
            raise ValueError("CHATBI_WEB_ORIGIN 必须是准确的网页 Origin")
        if parsed.scheme == "http" and (
            self.secure or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError("只有显式本地开发可以使用回环 HTTP 网页")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]):
        origin = environ.get("CHATBI_WEB_ORIGIN", "").strip()
        if not origin:
            if environ.get("CHATBI_WEB_DIST_DIR", "").strip():
                raise ValueError("配置网页目录时必须配置 CHATBI_WEB_ORIGIN")
            return None
        environment = environ.get("CHATBI_ENV", "").strip().lower()
        secure = not (
            environment in {"development", "dev", "test", "testing"}
            and origin.startswith("http://")
        )
        directory = environ.get("CHATBI_WEB_DIST_DIR", "").strip()
        return cls(origin, secure, Path(directory).resolve() if directory else None)


def reject_browser_request(
    request: Request, settings: BrowserSettings | None, *, write: bool
):
    if settings is None:
        raise HTTPException(503, "浏览器入口尚未配置")
    origin = request.headers.get("origin")
    site = request.headers.get("sec-fetch-site")
    if origin is not None and origin != settings.origin:
        raise HTTPException(403, "请求来源不允许")
    if site in {"cross-site", "same-site"}:
        raise HTTPException(403, "请求来源不允许")
    if write and (
        origin != settings.origin
        or request.headers.get("x-chatbi-request") != "browser"
        or request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(403, "浏览器请求校验失败")


def verify_expected_user(request: Request, context):
    if request.headers.get("x-chatbi-user-id") != str(context.user_id):
        raise AuthenticationRequired("登录身份已变化，请重新登录")


class BrowserIdentityProvider:
    identity_provider = "local"

    def __init__(self, auth_service, bearer_provider):
        self.auth_service = auth_service
        self.bearer_provider = bearer_provider

    def authenticate(self, request):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return self.bearer_provider.authenticate(request)
        if "authorization" in request.headers:
            raise AuthenticationRequired("不能混用登录凭证")
        try:
            context = self.auth_service.authenticate_session(token)
        except SessionExpired as exc:
            raise AuthenticationRequired("登录已过期，请重新登录") from exc
        except Exception as exc:
            raise IdentityProviderUnavailable("身份认证服务暂时不可用") from exc
        verify_expected_user(request, context)
        return context


class BrowserLoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: StrictStr
    password: StrictStr


class BrowserPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: StrictStr
    new_password: StrictStr


def _identity(context):
    return {
        "user_id": context.user_id,
        "username": context.username,
        "permissions": sorted(context.permissions),
        "must_change_password": context.must_change_password,
    }


def _auth_call(operation):
    try:
        return operation()
    except HTTPException:
        raise
    except (AuthenticationFailed, AuthenticationRequired) as exc:
        raise HTTPException(401, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception as exc:
        _LOGGER.warning(
            "Browser authentication failure: error_type=%s", type(exc).__name__
        )
        raise HTTPException(503, "身份认证服务暂时不可用") from None


def mount_browser_auth(app: FastAPI):
    def dependencies(request, *, write):
        settings = app.state.browser_settings
        reject_browser_request(request, settings, write=write)
        if "authorization" in request.headers:
            raise HTTPException(401, "浏览器接口不能使用 Bearer")
        auth = app.state.auth_service
        if auth is None:
            raise HTTPException(503, "身份认证服务暂时不可用")
        return settings, auth

    def token_from(request):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            raise HTTPException(401, "需要有效的身份认证")
        return token

    @app.post("/auth/browser/login")
    def login(request: Request, body: BrowserLoginBody, response: Response):
        settings, auth = dependencies(request, write=True)
        result = _auth_call(lambda: auth.login(body.username, body.password))
        response.set_cookie(
            COOKIE_NAME,
            result.token,
            httponly=True,
            secure=settings.secure,
            samesite="strict",
            path="/",
        )
        return _identity(result.auth_context)

    @app.get("/auth/browser/me")
    def me(request: Request):
        _, auth = dependencies(request, write=False)
        return _identity(
            _auth_call(lambda: auth.authenticate_session(token_from(request)))
        )

    @app.post("/auth/browser/logout", status_code=204)
    def logout(request: Request):
        settings, auth = dependencies(request, write=True)
        token = request.cookies.get(COOKIE_NAME)
        if token:

            def revoke():
                try:
                    context = auth.authenticate_session(token)
                except SessionExpired:
                    context = None
                if context is not None:
                    verify_expected_user(request, context)
                auth.logout(token)

            _auth_call(revoke)
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            secure=settings.secure,
            httponly=True,
            samesite="strict",
        )
        return response

    @app.post("/auth/browser/change-password", status_code=204)
    def change_password(request: Request, body: BrowserPasswordBody):
        settings, auth = dependencies(request, write=True)
        token = token_from(request)

        def change():
            context = auth.authenticate_session(token)
            verify_expected_user(request, context)
            auth.change_password(
                token,
                current_password=body.current_password,
                new_password=body.new_password,
            )

        _auth_call(change)
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            secure=settings.secure,
            httponly=True,
            samesite="strict",
        )
        return response


def mount_web_files(app: FastAPI, settings: BrowserSettings | None):
    if settings is None or settings.dist_dir is None:
        return
    directory = settings.dist_dir
    if not (directory / "index.html").is_file() or not (directory / "assets").is_dir():
        raise ValueError("CHATBI_WEB_DIST_DIR 缺少有效网页构建")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(
            directory / "index.html", headers={"Cache-Control": "no-cache"}
        )

    app.mount(
        "/assets",
        StaticFiles(directory=directory / "assets", follow_symlink=False),
        name="web-assets",
    )
