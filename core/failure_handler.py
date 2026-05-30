# -*- coding: utf-8 -*-
"""失败任务处理：记录 / 查询 / 标记 / 汇总（PostgreSQL）。

基于 task_failure_log 表。支撑需求 F15/F16/F17 与 retry 命令、status --failures。
error_type 枚举：token_invalid / network_timeout / rate_limit /
                permission_denied / data_error / unknown。
"""
import json
import logging

from config.settings import settings
from core.database import get_db_manager

logger = logging.getLogger(__name__)

T = settings.TBL_TASK_FAILURE_LOG


class FailureHandler:
    """失败任务处理器。"""

    def __init__(self):
        self.db = get_db_manager()

    # ---------- 记录 ----------
    def record_failure(self, collector, trade_date=None, ts_code=None,
                       error=None, error_type=None, context=None) -> int:
        """写入/累加 task_failure_log，返回记录 id。

        同 (collector, trade_date, ts_code) 的 pending 记录存在则累加 retry_count，
        否则新建。
        """
        etype = error_type or self._classify(error)
        emsg = str(error) if error else None
        ctx = json.dumps(context, ensure_ascii=False) if context else None

        existing = self.db.fetch_one(
            f"SELECT id, retry_count FROM {T} "
            f"WHERE collector=:c AND status='pending' "
            f"AND COALESCE(trade_date,'')=COALESCE(:d,'') "
            f"AND COALESCE(ts_code,'')=COALESCE(:s,'')",
            {"c": collector, "d": trade_date, "s": ts_code})

        if existing:
            self.db.execute(
                f"UPDATE {T} SET retry_count=retry_count+1, error_message=:m, "
                f"error_type=:t, updated_at=now() WHERE id=:id",
                {"m": emsg, "t": etype, "id": existing["id"]})
            return existing["id"]

        self.db.execute(
            f"INSERT INTO {T} (collector, trade_date, ts_code, error_type, "
            f"error_message, context, retry_count, status, created_at, updated_at) "
            f"VALUES (:c,:d,:s,:t,:m,:ctx,0,'pending',now(),now())",
            {"c": collector, "d": trade_date, "s": ts_code, "t": etype,
             "m": emsg, "ctx": ctx})
        logger.warning(f"记录失败: {collector} {ts_code} @ {trade_date} ({etype})")
        row = self.db.fetch_one(
            f"SELECT id FROM {T} WHERE collector=:c AND status='pending' "
            f"AND COALESCE(trade_date,'')=COALESCE(:d,'') "
            f"AND COALESCE(ts_code,'')=COALESCE(:s,'') ORDER BY id DESC LIMIT 1",
            {"c": collector, "d": trade_date, "s": ts_code})
        return row["id"] if row else -1

    def _classify(self, error) -> str:
        msg = (str(error) or "").lower()
        if any(k in msg for k in ("token", "密钥", "权限", "积分", "permission")):
            return "permission_denied" if "permission" in msg or "积分" in msg else "token_invalid"
        if any(k in msg for k in ("timeout", "connection", "network", "超时")):
            return "network_timeout"
        if any(k in msg for k in ("rate", "limit", "too many", "频率", "每分钟")):
            return "rate_limit"
        if any(k in msg for k in ("no data", "empty", "无数据")):
            return "data_error"
        return "unknown"

    # ---------- 查询 ----------
    def get_pending(self, collector=None, trade_date=None,
                    start_date=None, end_date=None) -> list:
        sql = f"SELECT * FROM {T} WHERE status='pending'"
        p = {}
        if collector:
            sql += " AND collector=:c"; p["c"] = collector
        if trade_date:
            sql += " AND trade_date=:d"; p["d"] = trade_date
        if start_date:
            sql += " AND trade_date>=:s"; p["s"] = start_date
        if end_date:
            sql += " AND trade_date<=:e"; p["e"] = end_date
        sql += " ORDER BY id"
        return self.db.fetch_all(sql, p)

    # ---------- 标记 ----------
    def mark_resolved(self, failure_id: int) -> None:
        self.db.execute(
            f"UPDATE {T} SET status='resolved', resolved_at=now(), updated_at=now() "
            f"WHERE id=:id", {"id": failure_id})

    def mark_resolved_batch(self, collector=None, trade_date=None) -> int:
        sql = (f"UPDATE {T} SET status='resolved', resolved_at=now(), "
               f"updated_at=now() WHERE status='pending'")
        p = {}
        if collector:
            sql += " AND collector=:c"; p["c"] = collector
        if trade_date:
            sql += " AND trade_date=:d"; p["d"] = trade_date
        return self.db.execute(sql, p)

    # ---------- 汇总 ----------
    def summary(self) -> dict:
        total_pending = self.db.count(T, "status='pending'")
        total_resolved = self.db.count(T, "status='resolved'")
        by_collector = {r["collector"]: r["c"] for r in self.db.fetch_all(
            f"SELECT collector, COUNT(*) AS c FROM {T} "
            f"WHERE status='pending' GROUP BY collector")}
        by_type = {r["error_type"]: r["c"] for r in self.db.fetch_all(
            f"SELECT error_type, COUNT(*) AS c FROM {T} "
            f"WHERE status='pending' GROUP BY error_type")}
        return {"total_pending": total_pending, "total_resolved": total_resolved,
                "by_collector": by_collector, "by_type": by_type}

    def print_report(self):
        s = self.summary()
        print("\n" + "=" * 60)
        print("失败任务报告")
        print("=" * 60)
        print(f"待处理: {s['total_pending']}  已解决: {s['total_resolved']}")
        if s["by_collector"]:
            print("\n按采集器:")
            for k, v in s["by_collector"].items():
                print(f"  {k}: {v}")
        if s["by_type"]:
            print("\n按错误类型:")
            for k, v in s["by_type"].items():
                print(f"  {k}: {v}")
        print("=" * 60)


def get_failure_handler() -> FailureHandler:
    """获取失败处理器实例（单例语义）。"""
    return FailureHandler()
