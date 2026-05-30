# -*- coding: utf-8 -*-
"""交易日历采集器（接口 trade_cal）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import SnapshotCollector

_FIELDS = "exchange,cal_date,is_open,pretrade_date"


class TradeCalendarCollector(SnapshotCollector):
    """各交易所交易日历，按年全量覆盖。"""

    TASK_NAME = "trade_calendar"
    TABLE_NAME = settings.TBL_TRADE_CALENDAR
    KEY_FIELDS = ["exchange", "cal_date"]
    REQUIRED_POINTS = 0

    def fetch_snapshot(self, start_date=None, end_date=None, **kwargs) -> pd.DataFrame:
        start_date = start_date or settings.data.start_date
        end_date = end_date or "20301231"   # 取到 2030 年，覆盖未来
        exchanges = ["SSE", "SZSE"]
        if settings.data.include_bse:
            exchanges.append("BSE")
        dfs = []
        for ex in exchanges:
            df = self.client.query("trade_cal", exchange=ex,
                                   start_date=start_date, end_date=end_date,
                                   fields=_FIELDS)
            if df is not None and not df.empty:
                dfs.append(df)
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # ---------- 查询辅助（命令层/检测层用）----------
    def is_trade_date(self, date: str, exchange: str = "SSE") -> bool:
        row = self.db.fetch_one(
            f"SELECT is_open FROM {self.TABLE_NAME} "
            f"WHERE exchange=:ex AND cal_date=:d", {"ex": exchange, "d": date})
        return bool(row and row.get("is_open") == 1)

    def get_previous_trade_date(self, date: str, exchange: str = "SSE"):
        row = self.db.fetch_one(
            f"SELECT pretrade_date FROM {self.TABLE_NAME} "
            f"WHERE exchange=:ex AND cal_date=:d", {"ex": exchange, "d": date})
        return row.get("pretrade_date") if row else None

    def get_next_trade_date(self, date: str, exchange: str = "SSE"):
        row = self.db.fetch_one(
            f"SELECT cal_date FROM {self.TABLE_NAME} "
            f"WHERE exchange=:ex AND is_open=1 AND cal_date>:d "
            f"ORDER BY cal_date LIMIT 1", {"ex": exchange, "d": date})
        return row.get("cal_date") if row else None
