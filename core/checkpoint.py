# -*- coding: utf-8 -*-
"""持久化采集工作项状态，用于中断后跳过已完整处理的工作项。"""
import logging

from sqlalchemy import text

from core.database import get_db_manager
from models.schema import collection_checkpoint

logger = logging.getLogger(__name__)


class CheckpointManager:
    """管理单个采集工作项的 claim、完成、失败与中断状态。"""

    def __init__(self):
        self.db = get_db_manager()
        # 新表通过 checkfirst 自动创建，兼容已部署的旧数据库。
        collection_checkpoint.create(self.db.engine, checkfirst=True)

    def claim(self, collector: str, item_type: str, item_key: str,
              force: bool = False):
        """领取工作项；已成功项目在非强制模式下返回 None。"""
        sql = text("""
            INSERT INTO collection_checkpoint
                (collector, item_type, item_key, status, attempt_count, started_at, updated_at)
            VALUES (:collector, :item_type, :item_key, 'running', 1, now(), now())
            ON CONFLICT (collector, item_type, item_key) DO UPDATE
            SET status='running',
                attempt_count=collection_checkpoint.attempt_count + 1,
                started_at=now(),
                updated_at=now(),
                last_error=NULL
            WHERE :force OR collection_checkpoint.status <> 'succeeded'
            RETURNING id
        """)
        with self.db.engine.begin() as conn:
            row = conn.execute(sql, {
                "collector": collector,
                "item_type": item_type,
                "item_key": item_key,
                "force": force,
            }).mappings().first()
        return dict(row) if row else None

    def mark_failed(self, checkpoint_id: int, error: Exception) -> None:
        self._mark_incomplete(checkpoint_id, "failed", str(error))

    def mark_interrupted(self, checkpoint_id: int) -> None:
        self._mark_incomplete(checkpoint_id, "interrupted", "用户中断")

    def _mark_incomplete(self, checkpoint_id: int, status: str, error: str) -> None:
        self.db.execute(
            "UPDATE collection_checkpoint "
            "SET status=:status, last_error=:error, updated_at=now() WHERE id=:id",
            {"id": checkpoint_id, "status": status, "error": error})


def get_checkpoint_manager() -> CheckpointManager:
    return CheckpointManager()
