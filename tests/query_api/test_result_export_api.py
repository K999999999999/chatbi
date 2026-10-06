from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from time import monotonic
from urllib.parse import unquote

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from src.authorization.contracts import AuthContext, AuthorizationDecision
from src.query_api.app import create_app
from src.query_api.export_runtime import ExportArtifact
from src.query_api.history_contracts import HistoryError


class Provider:
    identity_provider = "test"

    def authenticate(self, request):
        return AuthContext(
            "local:1", "test", user_id=1, permissions=frozenset({"query.execute"})
        )


class Policy:
    def authorize(self, context, **kwargs):
        return AuthorizationDecision(True, "AUTHORIZED", "test")


class Audit:
    def emit(self, event):
        pass


class Store:
    def __init__(self):
        self.calls = 0
        self.last_source = None

    def export_snapshot(self, owner, source_kind, source_id, turn_id):
        assert owner == 1
        self.calls += 1
        self.last_source = (source_kind, source_id, turn_id)
        return {
            "kind": "query",
            "title": f"测试结果 {self.calls}",
            "question": "销售额",
            "result_time": datetime(2026, 10, 6, tzinfo=UTC).isoformat(),
            "saved_time": (
                datetime(2026, 10, 6, tzinfo=UTC).isoformat()
                if source_kind == "saved_result"
                else None
            ),
            "result": {
                "columns": ["销售额"],
                "rows": [["10.25"]],
                "row_count": 1,
                "truncated": False,
                "result_metadata": None,
            },
        }


def make_client(store=None):
    app = create_app(
        service=object(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=store or Store(),
        history_runtime=object(),
    )
    return TestClient(app), app.state.result_export_runtime


def test_query_snapshot_download_has_safe_file_headers_and_current_source_check():
    client, runtime = make_client()
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 200, response.text
    book = load_workbook(BytesIO(response.content), read_only=True)
    assert list(book["原始数据"].values) == [("销售额",), ("10.25",)]
    assert ("来源问题", "销售额") in list(book["结果说明"].values)
    book.close()
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    filename = unquote(
        response.headers["content-disposition"].split("filename*=UTF-8''", 1)[1]
    )
    assert filename.startswith("测试结果 1-查询结果-") and filename.endswith(".xlsx")
    assert runtime._owner_active == set()


def test_saved_query_result_download_uses_the_independent_saved_source():
    store = Store()
    client, _ = make_client(store)
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 200, response.text
    assert store.last_source == (
        "saved_result",
        "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
        None,
    )
    book = load_workbook(BytesIO(response.content), read_only=True)
    notes = list(book["结果说明"].values)
    assert ("成果保存时间", "2026-10-06T00:00:00+00:00") in notes
    book.close()


def test_export_filename_removes_path_separators_and_header_controls():
    class UnsafeTitleStore(Store):
        def export_snapshot(self, owner, source_kind, source_id, turn_id):
            source = super().export_snapshot(owner, source_kind, source_id, turn_id)
            source["title"] = "../报告\r\n/X"
            return source

    client, _ = make_client(UnsafeTitleStore())
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 200, response.text
    header = response.headers["content-disposition"]
    filename = unquote(header.split("filename*=UTF-8''", 1)[1])
    assert filename.startswith("_报告___X-查询结果-") and filename.endswith(".xlsx")
    assert "/" not in filename and "\\" not in filename
    assert "\r" not in header and "\n" not in header


def test_export_rejects_unknown_fields_and_unimplemented_format():
    client, _ = make_client()
    with client:
        invalid_body = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
                "sql": "SELECT 1",
            },
        )
        missing_format = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "pdf",
            },
        )
    assert invalid_body.status_code == 422
    assert missing_format.status_code == 422
    assert missing_format.json()["error_code"] == "EXPORT_FORMAT_UNAVAILABLE"


def test_xlsx_export_rejects_saved_analysis_before_starting_worker():
    class AnalysisStore(Store):
        def export_snapshot(self, owner, source_kind, source_id, turn_id):
            assert owner == 1
            return {
                "kind": "analysis",
                "question": "分析问题",
                "result_time": None,
                "result": {"report": {}},
            }

    client, runtime = make_client(AnalysisStore())
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 422
    assert response.json()["error_code"] == "EXPORT_FORMAT_UNAVAILABLE"
    assert runtime._owner_active == set()


def test_png_export_accepts_analysis_and_passes_server_checked_selection(
    monkeypatch, tmp_path
):
    class AnalysisStore(Store):
        def export_snapshot(self, owner, source_kind, source_id, turn_id):
            self.calls += 1
            return {
                "kind": "analysis",
                "title": "经营分析",
                "question": "分析产品变化",
                "result_time": datetime(2026, 10, 6, tzinfo=UTC).isoformat(),
                "saved_time": None,
                "result": {
                    "mode": "analysis",
                    "report": {"attribution": {}},
                    "task_results": [],
                },
            }

    client, runtime = make_client(AnalysisStore())
    observed = {}
    artifact_dir = tmp_path / "png-artifact"
    artifact_dir.mkdir(mode=0o700)
    artifact_path = artifact_dir / "result.png"
    artifact_path.write_bytes(b"png-test")

    def generate(owner, document, cancelled, *, format, selection):
        observed.update(format=format, selection=selection, kind=document["kind"])
        return ExportArtifact(
            artifact_path, artifact_path.stat().st_size, monotonic() + 60
        )

    monkeypatch.setattr(runtime, "generate", generate)
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "png",
                "chart_id": "products",
                "chart_type": "bar",
            },
        )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    filename = unquote(
        response.headers["content-disposition"].split("filename*=UTF-8''", 1)[1]
    )
    assert filename.startswith("经营分析-图表-") and filename.endswith(".png")
    assert observed == {
        "format": "png",
        "selection": {"chart_id": "products", "chart_type": "bar"},
        "kind": "analysis",
    }


def test_pdf_export_accepts_only_analysis_and_returns_pdf_headers(monkeypatch, tmp_path):
    class AnalysisStore(Store):
        def export_snapshot(self, owner, source_kind, source_id, turn_id):
            return {
                "kind": "analysis",
                "title": "完整分析",
                "question": "分析十月经营情况",
                "result_time": datetime(2026, 10, 6, tzinfo=UTC).isoformat(),
                "saved_time": None,
                "result": {
                    "mode": "analysis",
                    "report": {"title": "完整分析", "task_results": []},
                    "task_results": [],
                },
            }

    client, runtime = make_client(AnalysisStore())
    artifact_dir = tmp_path / "pdf-artifact"
    artifact_dir.mkdir(mode=0o700)
    artifact_path = artifact_dir / "result.pdf"
    artifact_path.write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")

    def generate(owner, document, cancelled, *, format, selection):
        assert owner == 1
        assert format == "pdf"
        assert selection is None
        assert document["kind"] == "analysis"
        return ExportArtifact(artifact_path, artifact_path.stat().st_size, monotonic() + 60)

    monkeypatch.setattr(runtime, "generate", generate)
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "saved_result",
                    "saved_result_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                },
                "format": "pdf",
            },
        )
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF-")
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    filename = unquote(
        response.headers["content-disposition"].split("filename*=UTF-8''", 1)[1]
    )
    assert filename.startswith("完整分析-经营分析报告-") and filename.endswith(".pdf")
    assert runtime._owner_active == set()


def test_png_selection_is_required_and_forbidden_for_other_formats():
    client, _ = make_client()
    source = {
        "kind": "history_turn",
        "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
        "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
    }
    with client:
        missing = client.post(
            "/api/v1/result-exports", json={"source": source, "format": "png"}
        )
        extra = client.post(
            "/api/v1/result-exports",
            json={
                "source": source,
                "format": "xlsx",
                "chart_id": "CNY",
                "chart_type": "bar",
            },
        )
        unsupported = client.post(
            "/api/v1/result-exports", json={"source": source, "format": "pdf"}
        )
    assert missing.status_code == 422
    assert extra.status_code == 422
    assert unsupported.status_code == 422
    assert unsupported.json()["error_code"] == "EXPORT_FORMAT_UNAVAILABLE"


def test_renaming_source_while_rendering_does_not_change_snapshot_identity():
    client, _ = make_client()
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 200, response.text


def test_permission_revoked_before_download_discards_file_and_releases_quota():
    class RevokeAfterFirstCheck(Policy):
        checks = 0

        def authorize(self, context, **kwargs):
            self.checks += 1
            if self.checks == 2:
                return AuthorizationDecision(False, "AUTHORIZATION_DENIED", "denied")
            return super().authorize(context, **kwargs)

    app = create_app(
        service=object(),
        identity_provider=Provider(),
        policy_store=RevokeAfterFirstCheck(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=object(),
    )
    runtime = app.state.result_export_runtime
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTHORIZATION_DENIED"
    assert runtime._owner_active == set()


def test_source_deleted_before_delivery_discards_file_and_releases_quota():
    class DeletedStore(Store):
        def __init__(self):
            self.export_calls = 0
            super().__init__()

        def export_snapshot(self, owner, source_kind, source_id, turn_id):
            self.export_calls += 1
            if self.export_calls == 2:
                raise HistoryError("HISTORY_UNAVAILABLE", "unavailable", 404)
            return super().export_snapshot(owner, source_kind, source_id, turn_id)

    store = DeletedStore()
    app = create_app(
        service=object(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=store,
        history_runtime=object(),
    )
    runtime = app.state.result_export_runtime
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
        assert store.export_calls == 2
        assert response.status_code == 404
        assert runtime._owner_active == set()
        assert [path for path in runtime._root.iterdir() if path.is_dir()] == []


def test_export_rejected_when_owner_already_holds_generation_slot():
    client, runtime = make_client()
    assert runtime.acquire(1)
    with client:
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 429
    assert response.json()["error_code"] == "EXPORT_BUSY"
    runtime.release(1)


def test_cookie_export_request_requires_existing_csrf_contract():
    from src.query_api.browser import BrowserSettings

    app = create_app(
        service=object(),
        identity_provider=Provider(),
        policy_store=Policy(),
        audit_sink=Audit(),
        history_store=Store(),
        history_runtime=object(),
        browser_settings=BrowserSettings("http://127.0.0.1:5173", secure=False),
    )
    with TestClient(app) as client:
        client.cookies.set("chatbi_web_session", "unvalidated")
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 403


def test_export_runtime_startup_failure_does_not_block_other_api_routes(
    monkeypatch,
):
    client, runtime = make_client()

    def fail_startup():
        raise PermissionError("private temporary root unavailable")

    monkeypatch.setattr(runtime, "startup", fail_startup)
    with client:
        assert client.get("/health").status_code == 200
        response = client.post(
            "/api/v1/result-exports",
            json={
                "source": {
                    "kind": "history_turn",
                    "history_id": "e53ba3b9-1f11-4024-90f9-a7f2713cd56b",
                    "turn_id": "6e5e18d9-1d9b-4c6d-a94f-19976814f03f",
                },
                "format": "xlsx",
            },
        )
    assert response.status_code == 503
    assert response.json()["error_code"] == "EXPORT_UNAVAILABLE"
