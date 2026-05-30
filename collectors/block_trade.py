# -*- coding: utf-8 -*-
"""大宗交易采集器（接口 block_trade，2000 分）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = "ts_code,trade_date,price,vol,amount,buyer,seller"


class BlockTradeCollector(DateBasedCollector):
    """全市场大宗交易明细，按交易日采集。

    Tushare 无唯一 id，用 (ts_code, trade_date, price, vol) 近似去重。
    """

    TASK_NAME = "block_trade"
    TABLE_NAME = settings.TBL_BLOCK_TRADE
    KEY_FIELDS = ["ts_code", "trade_date", "price", "vol"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("block_trade", trade_date=trade_date, fields=_FIELDS)
