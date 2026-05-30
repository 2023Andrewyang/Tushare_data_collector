# -*- coding: utf-8 -*-
"""停复牌采集器（接口 suspend_d）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "ts_code,trade_date,suspend_timing,suspend_type"


class SuspendCollector(DateBasedCollector):
    """全市场当日停复牌信息，按交易日采集。"""

    TASK_NAME = "suspend"
    TABLE_NAME = settings.TBL_SUSPEND
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("suspend_d", trade_date=trade_date, fields=_FIELDS)
