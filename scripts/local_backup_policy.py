"""纯时间政策；运行期6小时、逾期24小时、成功后保留7天。"""

from datetime import datetime

INTERVAL = 6 * 3600
OVERDUE = 24 * 3600
RETENTION = 7 * 24 * 3600


def should_attempt(now, *, last_success=None, last_attempt=None, starting=False):
    if last_success is not None and last_success > now:
        last_success = None
    if starting and (
        last_success is None or (now - last_success).total_seconds() > OVERDUE
    ):
        return True
    if last_attempt is not None and (now - last_attempt).total_seconds() < INTERVAL:
        return False
    return last_success is None or (now - last_success).total_seconds() >= INTERVAL


def expired(entry, now):
    created = datetime.fromisoformat(entry["created_at"])
    if created.tzinfo is None:
        raise ValueError("备份时间必须包含时区")
    return (now - created).total_seconds() > RETENTION
