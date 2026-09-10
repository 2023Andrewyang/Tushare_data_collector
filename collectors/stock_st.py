# -*- coding: utf-8 -*-
"""ST 股票列表采集器（接口 stock_st，3000 分）。"""
import logging

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)

_FIELDS = "ts_code,name,trade_date,type,type_name"


class StockSTCollector(DateBasedCollector):
    """全市场当日 ST 列表，按交易日采集。ST 数据从 2016 年开始。"""

    TASK_NAME = "stock_st"
    TABLE_NAME = settings.TBL_STOCK_ST
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 3000

    DATA_START_DATE = "20160101"

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("stock_st", trade_date=trade_date, fields=_FIELDS)

    def run_full(self, start_date=None, end_date=None, _update=False, _force=False) -> dict:
        # ST 数据从 2016 年开始，早于此日期无数据
        if start_date is None or start_date < self.DATA_START_DATE:
            start_date = self.DATA_START_DATE
            logger.info(f"[{self.TASK_NAME}] ST 数据从 2016 年开始，"
                        f"调整起始日期为 {start_date}")
        return super().run_full(start_date, end_date, _update=_update, _force=_force)
