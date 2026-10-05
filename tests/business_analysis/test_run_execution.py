"""Guard覆盖整个调用者作用域；不按时间猜测原执行结束。"""

import pytest

from src.authorization.contracts import AuthContext
from src.business_analysis.run_execution import (
    AnalysisExecutionBusy,
    AnalysisExecutionGuard,
)


def test_shared_run_is_busy_until_finish_scope_exits():
    auth = AuthContext("local:1", "local", user_id=1)
    guard = AnalysisExecutionGuard()
    with guard.executing(auth, "run"):
        with pytest.raises(AnalysisExecutionBusy), guard.executing(auth, "run"):
            pytest.fail("不能进入同运行")
        with guard.executing(auth, "other-run"):
            pass
    with guard.executing(auth, "run"):
        pass
