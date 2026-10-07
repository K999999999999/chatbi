"""使用业务只读账号读取独立参考值；不调用模型、不输出连接配置。"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

from src.business_analysis.attribution import calculate_product_attribution
from src.business_analysis.contracts import AnalysisRequest, AnalysisTimeRange
from src.business_analysis.execution import TaskResult, TaskStatus
from src.online_query.query_understanding import TimeGranularity
from src.query_api.config import load_local_environment


def reference():
    import os

    load_local_environment()
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_APP_USER"],
        password=os.environ["POSTGRES_APP_PASSWORD"],
        autocommit=True,
    ) as connection:
        connection.read_only = True
        query = {}
        tasks = []
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            for month, period in ((2, "comparison"), (3, "current")):
                predicate = (
                    "f.order_status = 'completed' AND d.year = 2025 AND d.month = %s"
                )
                joins = "FROM mart_sales.fct_sales_order_line f JOIN mart_sales.dim_date d ON d.date_key = f.completion_date_key"
                cursor.execute(
                    f"SELECT SUM(f.net_sales_amount_cny), SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny) {joins} WHERE {predicate}",
                    (month,),
                )
                net, gross = cursor.fetchone()
                query[str(month)] = str(net)
                tasks.append(
                    TaskResult(
                        f"{period}-overall",
                        TaskStatus.COMPLETED,
                        ("人民币毛利",),
                        ((gross,),),
                        1,
                    )
                )
                cursor.execute(
                    f"SELECT p.product_name, SUM(f.net_sales_amount_cny), SUM(f.quantity), SUM(f.sales_cost_amount_cny) {joins} JOIN mart_sales.dim_product p ON p.product_key = f.product_key WHERE {predicate} GROUP BY p.product_name ORDER BY p.product_name",
                    (month,),
                )
                rows = tuple(cursor.fetchall())
                tasks.append(
                    TaskResult(
                        f"{period}-products",
                        TaskStatus.COMPLETED,
                        ("产品", "人民币净销售额", "已完成销售数量", "人民币销售成本"),
                        rows,
                        len(rows),
                    )
                )
            cursor.execute(
                "SELECT d.year, d.month, SUM(f.net_sales_amount_cny), SUM(f.net_sales_amount_cny-f.sales_cost_amount_cny), SUM(f.net_sales_amount_cny-f.sales_cost_amount_cny)/NULLIF(SUM(f.net_sales_amount_cny),0) FROM mart_sales.fct_sales_order_line f JOIN mart_sales.dim_date d ON d.date_key=f.completion_date_key WHERE f.order_status='completed' AND d.year=2025 GROUP BY d.year,d.month ORDER BY d.year,d.month"
            )
            monthly = {
                f"{year:04d}-{month:02d}-01": [
                    str(value) if value is not None else None for value in values
                ]
                for year, month, *values in cursor.fetchall()
            }
            cursor.execute(
                "SELECT p.product_line, SUM(f.net_sales_amount_cny), SUM(f.sales_cost_amount_cny) FROM mart_sales.fct_sales_order_line f JOIN mart_sales.dim_product p ON p.product_key=f.product_key JOIN mart_sales.dim_date d ON d.date_key=f.completion_date_key WHERE f.order_status='completed' AND d.year=2025 GROUP BY p.product_line ORDER BY p.product_line"
            )
            categories = {
                label: [str(net), str(cost)] for label, net, cost in cursor.fetchall()
            }
            cursor.execute(
                "SELECT p.product_name, SUM(f.net_sales_amount_cny) FROM mart_sales.fct_sales_order_line f JOIN mart_sales.dim_product p ON p.product_key=f.product_key JOIN mart_sales.dim_date d ON d.date_key=f.completion_date_key WHERE f.order_status='completed' AND d.year=2025 AND d.month=3 GROUP BY p.product_name ORDER BY SUM(f.net_sales_amount_cny) DESC NULLS FIRST,p.product_name ASC NULLS LAST LIMIT 3"
            )
            top_products = [[name, str(amount)] for name, amount in cursor.fetchall()]
    request = AnalysisRequest(
        "人民币毛利",
        AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
        AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
    )
    attribution = calculate_product_attribution(request, tuple(tasks)).to_payload()
    manifest = Path(
        os.environ.get(
            "CHATBI_CONTAINER_RAG_MANIFEST_PATH",
            str(Path(__file__).resolve().parents[1] / "data/rag/current.json"),
        )
    )
    runtime_identity = {
        "model": os.environ.get("LLM_MODEL"),
        "provider_host": urlsplit(os.environ.get("LLM_BASE_URL", "")).hostname,
        "rag_current_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()
        if manifest.is_file()
        else None,
        "schema": "mart_sales",
    }
    return {
        "net_sales": query,
        "monthly": monthly,
        "categories": categories,
        "top_products": top_products,
        "attribution": attribution,
        "runtime_identity": runtime_identity,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            reference(),
            ensure_ascii=False,
            default=lambda v: str(v) if isinstance(v, Decimal) else v,
        )
    )
