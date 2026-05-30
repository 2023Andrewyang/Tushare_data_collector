# -*- coding: utf-8 -*-
"""个股日线行情采集器（接口 daily）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,open,high,low,close,pre_close,"
           "change,pct_chg,vol,amount")


class DailyQuoteCollector(DateBasedCollector):
    """全市场日 OHLCV，按交易日采集。"""

    TASK_NAME = "daily_quote"
    TABLE_NAME = settings.TBL_DAILY_QUOTE
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("daily", trade_date=trade_date, fields=_FIELDS)

    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> dict:
        """按单只股票补采历史（用于数据修复）。"""
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        df = self.client.query("daily", ts_code=ts_code,
                               start_date=start_date, end_date=end_date, fields=_FIELDS)
        return self.save(df)
