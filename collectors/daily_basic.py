# -*- coding: utf-8 -*-
"""个股每日基本面指标采集器（接口 daily_basic）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,"
           "pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,"
           "free_share,total_mv,circ_mv")


class DailyBasicCollector(DateBasedCollector):
    """PE/PB、换手率、量比、市值，按交易日采集。"""

    TASK_NAME = "daily_basic"
    TABLE_NAME = settings.TBL_DAILY_BASIC
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("daily_basic", trade_date=trade_date, fields=_FIELDS)
