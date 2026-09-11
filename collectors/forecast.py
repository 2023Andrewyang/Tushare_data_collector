# -*- coding: utf-8 -*-
"""业绩预告采集器（接口 forecast，2000 分）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import PeriodBasedCollector

_FIELDS = ("ts_code,ann_date,end_date,type,p_change_min,p_change_max,"
           "net_profit_min,net_profit_max,last_parent_net,summary,change_reason")


class ForecastCollector(PeriodBasedCollector):
    """全市场业绩预告，按报告期采集。"""

    TASK_NAME = "forecast"
    TABLE_NAME = settings.TBL_FORECAST
    KEY_FIELDS = ["ts_code", "ann_date", "end_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_period(self, period: str) -> pd.DataFrame:
        return self.client.query("forecast", period=period, fields=_FIELDS)
