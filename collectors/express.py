# -*- coding: utf-8 -*-
"""业绩快报采集器（接口 express_vip，2000 分）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import PeriodBasedCollector

_FIELDS = ("ts_code,ann_date,end_date,revenue,operate_profit,total_profit,"
           "n_income,total_assets,yoy_sales,yoy_net_profit,diluted_roe")


class ExpressCollector(PeriodBasedCollector):
    """全市场业绩快报，按报告期采集。"""

    TASK_NAME = "express"
    TABLE_NAME = settings.TBL_EXPRESS
    KEY_FIELDS = ["ts_code", "ann_date", "end_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_period(self, period: str) -> pd.DataFrame:
        return self.client.query("express_vip", period=period, fields=_FIELDS)
