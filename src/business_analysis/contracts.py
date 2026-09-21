"""Business Analysis V1 的计划 Contract（契约）。"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from src.online_query.query_understanding import FilterOperator, TimeGranularity


class AnalysisTaskType(StrEnum):
    """V1 允许的单次查询任务类型。"""

    BASELINE = "baseline"
    TREND = "trend"
    BREAKDOWN = "breakdown"
    COMPARISON = "comparison"


class AnalysisPlanError(ValueError):
    """分析计划结构或业务校验失败。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class AnalysisPlanStructureError(AnalysisPlanError):
    """分析计划候选不符合结构化 Contract。"""


class AnalysisPlanCannotAnswer(AnalysisPlanError):
    """分析计划结构合法，但不能安全执行。"""


class AnalysisPlanClarificationRequired(AnalysisPlanError):
    """分析计划缺少唯一明确的业务语义。"""


class AnalysisPlanLLMError(RuntimeError):
    """Task Decomposer 的 Provider 或结构化输出失败。"""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AnalysisTimeRange:
    text: str
    granularity: TimeGranularity


@dataclass(frozen=True, slots=True)
class AnalysisFilter:
    field_text: str
    operator: FilterOperator
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisTaskCandidate:
    task_id: str
    task_type: AnalysisTaskType
    description: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    time_range: AnalysisTimeRange | None
    filters: tuple[AnalysisFilter, ...]
    depends_on: tuple[str, ...]
    expected_output: str


@dataclass(frozen=True, slots=True)
class AnalysisPlanCandidate:
    tasks: tuple[AnalysisTaskCandidate, ...]


@dataclass(frozen=True, slots=True)
class AnalysisTask:
    task_id: str
    task_type: AnalysisTaskType
    description: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    time_range: AnalysisTimeRange | None
    filters: tuple[AnalysisFilter, ...]
    depends_on: tuple[str, ...]
    expected_output: str


@dataclass(frozen=True, slots=True)
class AnalysisPlan:
    tasks: tuple[AnalysisTask, ...]


@dataclass(frozen=True, slots=True)
class AnalysisSemanticCatalog:
    """已确认的指标和维度名称及别名。"""

    metric_matches: Mapping[str, frozenset[str]]
    dimension_matches: Mapping[str, frozenset[str]]

    @classmethod
    def from_records(
        cls,
        metric_records: tuple[Mapping[str, object], ...],
        dimensions: tuple[str, ...],
    ) -> "AnalysisSemanticCatalog":
        metric_matches: dict[str, set[str]] = {}
        for record in metric_records:
            if not isinstance(record, Mapping):
                raise AnalysisPlanStructureError(
                    "指标事实必须是对象",
                    reason="METRIC_RECORD_INVALID",
                )
            name = _required_text(record.get("name"), "metric.name")
            aliases = record.get("aliases", [])
            if not isinstance(aliases, list):
                raise AnalysisPlanStructureError(
                    "指标 aliases 必须是数组",
                    reason="METRIC_ALIASES_INVALID",
                )
            for value in (name, *aliases):
                alias = _required_text(value, "metric.alias")
                metric_matches.setdefault(_lookup_key(alias), set()).add(name)

        dimension_matches: dict[str, set[str]] = {}
        for dimension in dimensions:
            name = _required_text(dimension, "dimension")
            dimension_matches.setdefault(_lookup_key(name), set()).add(name)

        return cls(
            metric_matches={
                key: frozenset(values) for key, values in metric_matches.items()
            },
            dimension_matches={
                key: frozenset(values)
                for key, values in dimension_matches.items()
            },
        )


@dataclass(frozen=True, slots=True)
class AnalysisDecompositionContext:
    current_time: str
    metric_records: tuple[Mapping[str, object], ...]
    dimensions: tuple[str, ...]


def _lookup_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalysisPlanStructureError(
            f"{field} 必须是非空字符串",
            reason="TEXT_REQUIRED",
        )
    return value.strip()
