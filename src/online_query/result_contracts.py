"""可兼容忽略的结果显示事实；没有Web、AST或数据库对象。"""

from dataclasses import dataclass
import json


@dataclass(frozen=True, slots=True)
class ResultMetadata:
    """持有独立JSON值快照，调用方不能变更已认证内容。"""

    payload_json: str

    @classmethod
    def from_payload(cls, payload: dict) -> "ResultMetadata":
        return cls(json.dumps(payload, ensure_ascii=False, allow_nan=False))

    def to_payload(self) -> dict:
        return json.loads(self.payload_json)
