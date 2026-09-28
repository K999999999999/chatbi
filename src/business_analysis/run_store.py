"""经营分析运行所有权、重放和 checkpoint 到期管理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import Engine, text

RUN_TTL = timedelta(hours=24)


class AnalysisRunConflict(ValueError):
    """运行 ID 已属于其他请求，或已超过可恢复期限。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AnalysisRunStatus:
    NEW = "new"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    analysis_run_id: UUID
    status: str


class PostgresAnalysisRunStore:
    """仅使用 chatbi_control 管理运行 ID 元数据和 checkpoint TTL。"""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def close(self) -> None:
        self._engine.dispose()

    def claim(
        self,
        analysis_run_id: UUID,
        *,
        owner_subject: str,
        question: str,
        now: datetime | None = None,
    ) -> AnalysisRun:
        moment = now or datetime.now(UTC)
        fingerprint = sha256(question.strip().encode("utf-8")).hexdigest()
        with self._engine.begin() as connection:
            inserted = connection.execute(
                text(
                    """INSERT INTO business_analysis_runs (
                           analysis_run_id, owner_subject, question_sha256, status,
                           expires_at
                       ) VALUES (:run_id, :owner, :question_hash, 'active', :expires_at)
                       ON CONFLICT (analysis_run_id) DO NOTHING"""
                ),
                {
                    "run_id": str(analysis_run_id),
                    "owner": owner_subject,
                    "question_hash": fingerprint,
                    "expires_at": moment + RUN_TTL,
                },
            )
            row = (
                connection.execute(
                    text(
                        """SELECT owner_subject, question_sha256, status, expires_at
                       FROM business_analysis_runs
                       WHERE analysis_run_id = :run_id
                       FOR UPDATE"""
                    ),
                    {"run_id": str(analysis_run_id)},
                )
                .mappings()
                .one()
            )

            if row["owner_subject"] != owner_subject:
                raise AnalysisRunConflict("ANALYSIS_RUN_OWNER_MISMATCH")
            if row["question_sha256"] != fingerprint:
                raise AnalysisRunConflict("ANALYSIS_RUN_QUESTION_MISMATCH")
            if row["status"] == "expired" or row["expires_at"] <= moment:
                raise AnalysisRunConflict("ANALYSIS_RUN_EXPIRED")

            status = AnalysisRunStatus.NEW if inserted.rowcount == 1 else row["status"]
            return AnalysisRun(analysis_run_id, status)

    def mark_completed(
        self,
        analysis_run_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        with self._engine.begin() as connection:
            result = connection.execute(
                text(
                    """UPDATE business_analysis_runs
                       SET status = 'completed', updated_at = :now
                       WHERE analysis_run_id = :run_id AND status = 'active'"""
                ),
                {
                    "now": now or datetime.now(UTC),
                    "run_id": str(analysis_run_id),
                },
            )
            if result.rowcount != 1:
                raise AnalysisRunConflict("ANALYSIS_RUN_STATE_CONFLICT")

    def cleanup_expired(self, *, now: datetime | None = None) -> int:
        moment = now or datetime.now(UTC)
        with self._engine.begin() as connection:
            run_ids = tuple(
                row[0]
                for row in connection.execute(
                    text(
                        """UPDATE business_analysis_runs
                           SET status = 'expired', updated_at = :now
                           WHERE expires_at <= :now AND status <> 'expired'
                           RETURNING analysis_run_id"""
                    ),
                    {"now": moment},
                )
            )
            for run_id in run_ids:
                for table in (
                    "checkpoint_writes",
                    "checkpoint_blobs",
                    "checkpoints",
                ):
                    connection.execute(
                        text(f"DELETE FROM {table} WHERE thread_id = :run_id"),
                        {"run_id": str(run_id)},
                    )
        return len(run_ids)
