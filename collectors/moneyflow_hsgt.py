# -*- coding: utf-8 -*-
"""北向/南向资金采集器（接口 moneyflow_hsgt，2000 分）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "trade_date,ggt_ss,ggt_sz,hgt,sgt,north_money,south_money"


class MoneyflowHsgtCollector(DateBasedCollector):
    """沪深股通资金流向，当日仅 1 条，按交易日采集。"""

    TASK_NAME = "moneyflow_hsgt"
    TABLE_NAME = settings.TBL_MONEYFLOW_HSGT
    KEY_FIELDS = ["trade_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("moneyflow_hsgt", trade_date=trade_date, fields=_FIELDS)
