# -*- coding: utf-8 -*-
"""涨跌停"价格"采集器（接口 stk_limit）。

注意：这是涨跌停"价格"，与 limit_list（涨跌停"列表"）不同（修复 D1）。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "ts_code,trade_date,pre_close,up_limit,down_limit"


class StkLimitCollector(DateBasedCollector):
    """全市场每日涨跌停价格，按交易日采集。"""

    TASK_NAME = "stk_limit"
    TABLE_NAME = settings.TBL_STK_LIMIT
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("stk_limit", trade_date=trade_date, fields=_FIELDS)
