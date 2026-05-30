# -*- coding: utf-8 -*-
"""指数日线行情采集器（接口 index_daily + index_dailybasic）。

固定采集 8 个核心指数。index_daily 基础 K 线（120分），
若积分 >= 2000 则额外 merge index_dailybasic 的 pe/pb/市值。
"""
import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

_DAILY_FIELDS = ("ts_code,trade_date,close,open,high,low,pre_close,"
                 "change,pct_chg,vol,amount")
_BASIC_FIELDS = "ts_code,trade_date,pe,pb,total_mv,float_mv"

# 上证、深成、创业板、科创50、沪深300、中证500、中证1000、北证50
INDEX_CODES = ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH",
               "000300.SH", "000905.SH", "000852.SH", "899050.BJ"]


class IndexDailyCollector(DateBasedCollector):
    """核心指数日线 + 每日指标，按交易日采集。"""

    TASK_NAME = "index_daily"
    TABLE_NAME = settings.TBL_INDEX_DAILY
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        dfs = []
        for code in INDEX_CODES:
            df = self.client.query("index_daily", ts_code=code,
                                   trade_date=trade_date, fields=_DAILY_FIELDS)
            if df is not None and not df.empty:
                dfs.append(df)
        if not dfs:
            return pd.DataFrame()
        kline = pd.concat(dfs, ignore_index=True)

        # index_dailybasic 需要 2000 分，按交易日一次取全部指数
        if self.client.points >= 2000:
            basic = self.client.query("index_dailybasic", trade_date=trade_date,
                                      fields=_BASIC_FIELDS)
            if basic is not None and not basic.empty:
                basic = basic[basic["ts_code"].isin(INDEX_CODES)]
                if not basic.empty:
                    kline = kline.merge(basic, on=["ts_code", "trade_date"], how="left")
        return kline
