"""使用业务只读账号读取独立参考值；不调用模型、不输出连接配置。"""

import json
from decimal import Decimal

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
    request = AnalysisRequest(
        "人民币毛利",
        AnalysisTimeRange("2025年3月", TimeGranularity.MONTH),
        AnalysisTimeRange("2025年2月", TimeGranularity.MONTH),
    )
    attribution = calculate_product_attribution(request, tuple(tasks)).to_payload()
    return {"net_sales": query, "attribution": attribution}


if __name__ == "__main__":
    print(
        json.dumps(
            reference(),
            ensure_ascii=False,
            default=lambda v: str(v) if isinstance(v, Decimal) else v,
        )
    )
