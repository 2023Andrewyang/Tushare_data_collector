# -*- coding: utf-8 -*-
"""东方财富板块 K 线采集器（接口 dc_daily，6000 分）。

字段以 Tushare 官方 dc_daily 文档为准。积分不足时由基类自动跳过。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,open,high,low,close,change,pct_change,"
           "vol,amount,swing,turnover_rate")


class DcDailyCollector(DateBasedCollector):
    """东财板块 OHLC + 量额 + 振幅 + 换手，按交易日采集。"""

    TASK_NAME = "dc_daily"
    TABLE_NAME = settings.TBL_DC_SECTOR_KLINE
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 6000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("dc_daily", trade_date=trade_date, fields=_FIELDS)
