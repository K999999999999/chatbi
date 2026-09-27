"""确定性判定未限定利润口径的业务歧义。"""

_EXPLICIT_PROFIT_METRICS = ("毛利", "毛利率", "净利润")


def requires_metric_clarification(question: str) -> bool:
    """未限定的“利润”不能由模型自行映射到某个指标。"""

    compact_question = "".join(question.split())
    return "利润" in compact_question and not any(
        metric in compact_question for metric in _EXPLICIT_PROFIT_METRICS
    )
