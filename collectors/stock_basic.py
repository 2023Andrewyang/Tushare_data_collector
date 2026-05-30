# -*- coding: utf-8 -*-
"""股票基础信息采集器（接口 stock_basic）。"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import SnapshotCollector

_FIELDS = ("ts_code,symbol,name,area,industry,fullname,market,exchange,"
           "curr_type,list_status,list_date,delist_date,is_hs")


class StockBasicCollector(SnapshotCollector):
    """全市场 A 股基础信息，全量快照（约 5500 条）。"""

    TASK_NAME = "stock_basic"
    TABLE_NAME = settings.TBL_STOCK_BASIC
    KEY_FIELDS = ["ts_code"]
    REQUIRED_POINTS = 0

    def fetch_snapshot(self, **kwargs) -> pd.DataFrame:
        dfs = []
        for status in ("L", "D", "P"):
            df = self.client.query("stock_basic", list_status=status, fields=_FIELDS)
            if df is not None and not df.empty:
                dfs.append(df)
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
