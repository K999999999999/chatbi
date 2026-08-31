"""Evaluation（标准回归评测）公共入口。"""

from .evaluator import (
    EvaluationCase,
    EvaluationLoadError,
    load_evaluation_cases,
    results_match,
)

__all__ = [
    "EvaluationCase",
    "EvaluationLoadError",
    "load_evaluation_cases",
    "results_match",
]
