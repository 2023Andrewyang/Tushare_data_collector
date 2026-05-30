# -*- coding: utf-8 -*-
"""涨跌停"列表"采集器（接口 limit_list_d，2000 分）。

注意：这是涨停/跌停/炸板的股票"名单"，与 stk_limit（涨跌停价格）不同（修复 D1）。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,name,close,pct_chg,amount,limit_amount,"
           "float_mv,total_mv,turnover_ratio,fd_amount,first_time,last_time,"
           "open_times,up_stat,limit_times,limit")


class LimitListCollector(DateBasedCollector):
    """当日涨停/跌停/炸板名单，按交易日采集。"""

    TASK_NAME = "limit_list"
    TABLE_NAME = settings.TBL_LIMIT_LIST
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("limit_list_d", trade_date=trade_date, fields=_FIELDS)
