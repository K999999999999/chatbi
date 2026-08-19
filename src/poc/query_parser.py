"""POC 查询解析：只做输入校验，不替代 LLM 理解业务问题。"""

from __future__ import annotations

from dataclasses import dataclass


class QueryParseError(ValueError):
    """用户输入不满足最小查询契约。"""


@dataclass(frozen=True)
class ParsedQuery:
    """保留原始自然语言问题的最小结构。"""

    question: str


class QueryParser:
    """按照教程的 MVP 边界，只负责非空校验。"""

    def parse(self, user_input: str) -> ParsedQuery:
        normalized = user_input.strip()
        if not normalized:
            raise QueryParseError("用户问题不能为空")
        return ParsedQuery(question=normalized)
