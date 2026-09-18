"""授权审计 Sink 的本地、可替换实现。"""

from dataclasses import dataclass, field

from .contracts import AuthorizationAuditEvent


@dataclass
class InMemoryAuditSink:
    """供本地 Demo 和确定性测试使用的进程内事件收集器。"""

    events: list[AuthorizationAuditEvent] = field(default_factory=list)

    def emit(self, event: AuthorizationAuditEvent) -> None:
        self.events.append(event)
