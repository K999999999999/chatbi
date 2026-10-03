"""真实服务认证结果通过受保护API公开，额外字段不改变会话与行值。"""

from dataclasses import replace
from fastapi.testclient import TestClient
from tests.query_api.support import create_test_app
from tests.online_query.test_result_metadata import query


def test_certified_result_metadata_is_optional_public_addition():
    result = query(
        "SELECT SUM(f.net_sales_amount_cny) AS arbitrary FROM mart_sales.fct_sales_order_line f WHERE f.order_status='completed'"
    )

    class Service:
        def execute(self, request):
            return replace(result, request_id=request.request_id)

    client = TestClient(create_test_app(Service()))
    response = client.post(
        "/api/v1/query",
        json={"question": "人民币净销售额"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["arbitrary"]
    assert body["row_count"] == 1
    assert body["conversation_id"]
    assert body["result_metadata"]["columns"][0]["unit"] == {
        "key": "CNY",
        "label": "元",
    }
    assert body["result_metadata"]["scope"]["time_status"] == "unbounded"
