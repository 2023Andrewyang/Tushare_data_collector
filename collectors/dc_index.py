# -*- coding: utf-8 -*-
"""东方财富板块每日快照采集器（接口 dc_index，6000 分）。

字段以 Tushare 官方 dc_index 文档为准。本实现按预估 schema 列取数，
积分不足时由基类自动跳过。如官方字段与此不符，调整 _FIELDS 与 schema 后即可。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_FIELDS = ("ts_code,trade_date,name,leading,leading_code,pct_change,leading_pct,"
           "total_mv,turnover_rate,up_num,down_num")


class DcIndexCollector(DateBasedCollector):
    """东财行业/概念/地域板块每日快照，按交易日采集。"""

    TASK_NAME = "dc_index"
    TABLE_NAME = settings.TBL_DC_SECTOR_DAILY
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 6000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        return self.client.query("dc_index", trade_date=trade_date, fields=_FIELDS)
