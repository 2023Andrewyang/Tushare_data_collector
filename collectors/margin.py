# -*- coding: utf-8 -*-
"""融资融券汇总采集器（接口 margin，2000 分）。

按交易所汇总，主键 (trade_date, exchange_id)（修复 D3）。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "trade_date,exchange_id,rzye,rzmre,rqye,rqmcl,rzche,rqyl,rqchl,rzrqye"


class MarginCollector(DateBasedCollector):
    """融资融券交易所汇总，当日各交易所一行，按交易日采集。"""

    TASK_NAME = "margin"
    TABLE_NAME = settings.TBL_MARGIN_SUMMARY
    KEY_FIELDS = ["trade_date", "exchange_id"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("margin", trade_date=trade_date, fields=_FIELDS)
