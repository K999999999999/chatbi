"""完整结构化业务状态；不包含SQL或身份。"""


def query_state():
    return {
        "state_version": 1,
        "semantic_query": {
            "query_type": "metric_analysis",
            "subjects": [],
            "metrics": ["人民币净销售额"],
            "dimensions": [],
            "time": None,
            "filters": [],
            "conditions": {
                "order_by": [],
                "row_limit": None,
                "aggregate_filters": [],
                "selection": None,
            },
        },
        "provenance": {"metrics": [], "bindings": {}, "columns": {}, "joins": []},
    }
