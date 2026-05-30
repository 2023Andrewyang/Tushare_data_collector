# -*- coding: utf-8 -*-
"""个股资金流向采集器（接口 moneyflow，2000 分）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,"
           "buy_sm_vol,buy_sm_amount,sell_sm_vol,sell_sm_amount,"
           "buy_md_vol,buy_md_amount,sell_md_vol,sell_md_amount,"
           "buy_lg_vol,buy_lg_amount,sell_lg_vol,sell_lg_amount,"
           "buy_elg_vol,buy_elg_amount,sell_elg_vol,sell_elg_amount,"
           "net_mf_vol,net_mf_amount")


class MoneyflowCollector(DateBasedCollector):
    """全市场个股资金流向（各档买卖量额、净流入），按交易日采集。"""

    TASK_NAME = "moneyflow"
    TABLE_NAME = settings.TBL_MONEYFLOW
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("moneyflow", trade_date=trade_date, fields=_FIELDS)
