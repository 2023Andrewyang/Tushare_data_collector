# -*- coding: utf-8 -*-
"""采集器基类：幂等写入 + 失败记录 + 积分门控 + 列对齐清洗。

提供 4 个基类，封装所有「循环 / 幂等写入 / 失败记录 / 积分门控 / 列对齐清洗」逻辑：
- DateBasedCollector    子类实现 fetch_by_date(trade_date)
- StockBasedCollector   子类实现 fetch_by_stock(ts_code, start, end)
- PeriodBasedCollector  子类实现 fetch_by_period(period)
- SnapshotCollector     子类实现 fetch_snapshot(**kwargs)

子类只负责「给定参数 -> 返回干净的 DataFrame」，不写循环/进度/失败/清洗。
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import settings
from core.database import get_db_manager
from core.tushare_client import get_tushare_client
from core.failure_handler import get_failure_handler
from models.schema import TABLES

logger = logging.getLogger(__name__)

DATE_COLS = {"trade_date", "cal_date", "ann_date", "end_date",
             "list_date", "delist_date", "pretrade_date", "snapshot_date"}


class BaseCollector(ABC):
    """采集器抽象基类。"""

    TASK_NAME: str = None        # 任务名，与表名/接口名一致
    TABLE_NAME: str = None       # 目标表名
    KEY_FIELDS: list = []        # 主键字段
    REQUIRED_POINTS: int = 0     # 该接口所需积分门槛，无门槛填 0

    def __init__(self):
        self.db = get_db_manager()
        self.client = get_tushare_client()
        self.failure = get_failure_handler()
        if not self.TASK_NAME or not self.TABLE_NAME:
            raise ValueError(f"{type(self).__name__} 未设置 TASK_NAME/TABLE_NAME")

    # ---------- 积分门控 ----------
    def can_run(self) -> bool:
        if self.client.points < self.REQUIRED_POINTS:
            logger.warning(f"[{self.TASK_NAME}] 积分不足"
                           f"（需要 {self.REQUIRED_POINTS}，当前 {self.client.points}），跳过")
            return False
        return True

    # ---------- 列对齐 + 清洗（90 文档第九节）----------
    def align_columns(self, df: pd.DataFrame, table_name: str = None) -> pd.DataFrame:
        """按 schema 表列裁剪/补齐 DataFrame，并做日期->str、NaN->None 清洗。

        table_name 默认用 self.TABLE_NAME；top_list 等需写多表时可显式传入。
        """
        if df is None or df.empty:
            return pd.DataFrame()
        table = TABLES[table_name or self.TABLE_NAME]
        cols = [c.name for c in table.columns if c.name != "created_at"]
        df = df.copy()
        # 补缺列
        for c in cols:
            if c not in df.columns:
                df[c] = None
        # 丢多余列
        df = df[[c for c in cols if c in df.columns]].copy()
        # 日期列转字符串
        for c in df.columns:
            if c in DATE_COLS:
                df[c] = df[c].apply(
                    lambda v: None if pd.isna(v) else str(v).split(".")[0])
        # NaN -> None
        df = df.replace({np.nan: None})
        # pandas 可能残留 NaT/<NA>，统一兜底
        df = df.where(pd.notna(df), None)
        return df

    # ---------- 写入 ----------
    def save(self, df: pd.DataFrame, update_on_conflict: bool = False,
             table_name: str = None, key_fields: list = None) -> dict:
        df = self.align_columns(df, table_name)
        if df.empty:
            return {"success": 0, "failed": 0}
        rows = df.to_dict("records")
        r = self.db.bulk_upsert(table_name or self.TABLE_NAME, rows,
                                key_fields or self.KEY_FIELDS, update_on_conflict)
        logger.info(f"[{self.TASK_NAME}] 写入 {r['affected']}/{r['received']}")
        return {"success": r["affected"], "failed": 0}

    # ---------- 失败 ----------
    def record_failure(self, trade_date=None, ts_code=None, error=None, context=None):
        self.failure.record_failure(self.TASK_NAME, trade_date=trade_date,
                                    ts_code=ts_code, error=error, context=context)

    # ---------- 公共查询 ----------
    def get_trade_dates(self, start_date, end_date, exchange="SSE") -> list:
        rows = self.db.fetch_all(
            f"SELECT cal_date FROM {settings.TBL_TRADE_CALENDAR} "
            f"WHERE exchange=:ex AND is_open=1 AND cal_date>=:s AND cal_date<=:e "
            f"ORDER BY cal_date", {"ex": exchange, "s": start_date, "e": end_date})
        return [r["cal_date"] for r in rows]

    def get_stock_codes(self, only_listed=False) -> list:
        where = "list_status='L'" if only_listed else None
        sql = f"SELECT ts_code FROM {settings.TBL_STOCK_BASIC}"
        if where:
            sql += f" WHERE {where}"
        return [r["ts_code"] for r in self.db.fetch_all(sql)]

    def get_today(self) -> str:
        return datetime.now().strftime("%Y%m%d")

    # ---------- 顶层入口（命令层调用）----------
    @abstractmethod
    def run_full(self, start_date=None, end_date=None) -> dict: ...

    @abstractmethod
    def run_incremental(self, trade_date=None) -> dict: ...

    def run_backfill(self, start_date, end_date) -> dict:
        """默认：等同 run_full 但强制覆盖写。子类一般无需重写。"""
        return self.run_full(start_date, end_date, _update=True)


class DateBasedCollector(BaseCollector):
    """按交易日批量取全市场数据（daily、daily_basic、moneyflow…）。"""

    @abstractmethod
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame: ...

    def run_full(self, start_date=None, end_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        dates = self.get_trade_dates(start_date, end_date)
        if not dates:
            logger.warning(f"[{self.TASK_NAME}] 无交易日（请先同步 trade_calendar）")
            return {"success": 0, "failed": 0}
        total_s = total_f = 0
        t0 = datetime.now()
        for i, d in enumerate(dates):
            try:
                df = self.fetch_by_date(d)
                r = self.save(df, update_on_conflict=_update)
                total_s += r["success"]
            except KeyboardInterrupt:
                logger.warning(f"[{self.TASK_NAME}] 用户中断于 {d}")
                raise
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] {d} 失败: {e}")
                self.record_failure(trade_date=d, error=e)
                total_f += 1
            if (i + 1) % 50 == 0:
                logger.info(f"[{self.TASK_NAME}] {i + 1}/{len(dates)}")
        return {"success": total_s, "failed": total_f,
                "duration": (datetime.now() - t0).total_seconds()}

    def run_incremental(self, trade_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        d = trade_date or self.get_today()
        try:
            df = self.fetch_by_date(d)
            return self.save(df, update_on_conflict=_update)
        except Exception as e:
            logger.error(f"[{self.TASK_NAME}] 增量 {d} 失败: {e}")
            self.record_failure(trade_date=d, error=e)
            return {"success": 0, "failed": 1}


class StockBasedCollector(BaseCollector):
    """按个股代码取数（少用）。"""

    @abstractmethod
    def fetch_by_stock(self, ts_code: str, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame: ...

    def run_full(self, start_date=None, end_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        codes = self.get_stock_codes()
        if not codes:
            logger.warning(f"[{self.TASK_NAME}] 无股票列表（请先同步 stock_basic）")
            return {"success": 0, "failed": 0}
        total_s = total_f = 0
        t0 = datetime.now()
        for i, code in enumerate(codes):
            try:
                df = self.fetch_by_stock(code, start_date, end_date)
                r = self.save(df, update_on_conflict=_update)
                total_s += r["success"]
            except KeyboardInterrupt:
                logger.warning(f"[{self.TASK_NAME}] 用户中断于 {code}")
                raise
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] {code} 失败: {e}")
                self.record_failure(ts_code=code, error=e)
                total_f += 1
            if (i + 1) % 100 == 0:
                logger.info(f"[{self.TASK_NAME}] {i + 1}/{len(codes)}")
        return {"success": total_s, "failed": total_f,
                "duration": (datetime.now() - t0).total_seconds()}

    def run_incremental(self, trade_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        d = trade_date or self.get_today()
        codes = self.get_stock_codes(only_listed=True)
        total_s = total_f = 0
        for code in codes:
            try:
                df = self.fetch_by_stock(code, d, d)
                r = self.save(df, update_on_conflict=_update)
                total_s += r["success"]
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] 增量 {code} 失败: {e}")
                self.record_failure(ts_code=code, trade_date=d, error=e)
                total_f += 1
        return {"success": total_s, "failed": total_f}


class PeriodBasedCollector(BaseCollector):
    """按财报报告期取数（fina_indicator、forecast、express）。"""

    @abstractmethod
    def fetch_by_period(self, period: str) -> pd.DataFrame: ...

    def gen_periods(self, start_date, end_date) -> list:
        sy, ey = int(start_date[:4]), int(end_date[:4])
        out = []
        for y in range(sy, ey + 1):
            for q in ("0331", "0630", "0930", "1231"):
                p = f"{y}{q}"
                if start_date <= p <= end_date:
                    out.append(p)
        return sorted(out)

    def run_full(self, start_date=None, end_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        periods = self.gen_periods(start_date, end_date)
        total_s = total_f = 0
        t0 = datetime.now()
        for p in periods:
            try:
                df = self.fetch_by_period(p)
                r = self.save(df, update_on_conflict=_update)
                total_s += r["success"]
            except KeyboardInterrupt:
                logger.warning(f"[{self.TASK_NAME}] 用户中断于报告期 {p}")
                raise
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] 报告期 {p} 失败: {e}")
                self.record_failure(trade_date=p, error=e)
                total_f += 1
        return {"success": total_s, "failed": total_f,
                "duration": (datetime.now() - t0).total_seconds()}

    def run_incremental(self, trade_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        # 若传入的是单个报告期（retry 场景），直接采该报告期
        if trade_date and len(str(trade_date)) == 8 and str(trade_date).endswith(
                ("0331", "0630", "0930", "1231")):
            periods = [trade_date]
        else:
            periods = self._recent_periods(n=2)
        total_s = total_f = 0
        for p in periods:
            try:
                r = self.save(self.fetch_by_period(p), update_on_conflict=_update)
                total_s += r["success"]
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] 增量报告期 {p} 失败: {e}")
                self.record_failure(trade_date=p, error=e)
                total_f += 1
        return {"success": total_s, "failed": total_f}

    def _recent_periods(self, n=2) -> list:
        today = datetime.now()
        y, m = today.year, today.month
        latest = (f"{y}0930" if m >= 10 else f"{y}0630" if m >= 7
                  else f"{y}0331" if m >= 4 else f"{y - 1}1231")
        allp = self.gen_periods(f"{y - 2}0101", f"{y}1231")
        try:
            i = allp.index(latest)
            return allp[max(0, i - n + 1):i + 1]
        except ValueError:
            return allp[-n:]


class SnapshotCollector(BaseCollector):
    """全量快照类（stock_basic、trade_calendar、dc_member）。"""

    @abstractmethod
    def fetch_snapshot(self, **kwargs) -> pd.DataFrame: ...

    def run_full(self, start_date=None, end_date=None, _update=False) -> dict:
        if not self.can_run():
            return {"success": 0, "failed": 0, "skipped": True}
        try:
            df = self.fetch_snapshot(start_date=start_date, end_date=end_date)
            # 快照默认覆盖写，保证最新
            return self.save(df, update_on_conflict=True)
        except Exception as e:
            logger.error(f"[{self.TASK_NAME}] 快照采集失败: {e}")
            self.record_failure(error=e)
            return {"success": 0, "failed": 1}

    def run_incremental(self, trade_date=None, _update=False) -> dict:
        return self.run_full()
