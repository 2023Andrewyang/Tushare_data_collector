# -*- coding: utf-8 -*-
"""东方财富板块成分股采集器（接口 dc_member，6000 分，每周快照）。

字段以 Tushare 官方 dc_member 文档为准。积分不足时由基类自动跳过。
给每行打 snapshot_date（最近交易日/今日），保留历史快照。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import SnapshotCollector

_FIELDS = "ts_code,con_code,name,trade_date"


class DcMemberCollector(SnapshotCollector):
    """东财所有板块当前成分股，带快照日期。"""

    TASK_NAME = "dc_member"
    TABLE_NAME = settings.TBL_DC_SECTOR_MEMBER
    KEY_FIELDS = ["snapshot_date", "ts_code", "con_code"]
    REQUIRED_POINTS = 6000

    def fetch_snapshot(self, start_date=None, end_date=None, **kwargs) -> pd.DataFrame:
        snapshot_date = end_date or self.get_today()
        df = self.client.query("dc_member", trade_date=snapshot_date, fields=_FIELDS)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["snapshot_date"] = snapshot_date
        return df
