# -*- coding: utf-8 -*-
"""复权因子采集器（接口 adj_factor）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "ts_code,trade_date,adj_factor"


class AdjFactorCollector(DateBasedCollector):
    """全市场复权因子，按交易日采集。"""

    TASK_NAME = "adj_factor"
    TABLE_NAME = settings.TBL_ADJ_FACTOR
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("adj_factor", trade_date=trade_date, fields=_FIELDS)
