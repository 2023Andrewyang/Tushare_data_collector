# -*- coding: utf-8 -*-
"""采集器基类测试（单元，不连库）。

align_columns 只依赖 schema 与 TABLE_NAME，不用 db/client，
因此通过 __new__ 绕过需要连库的 __init__，直接测试清洗逻辑。
"""
import pandas as pd

from collectors.base_collector import DateBasedCollector


class _Fake(DateBasedCollector):
    TASK_NAME = "daily_quote"
    TABLE_NAME = "daily_quote"
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 0

    def fetch_by_date(self, d):
        return pd.DataFrame([{
            "ts_code": "X.SZ", "trade_date": d, "close": 1.23,
            "extra_col": "drop_me", "vol": float("nan")}])


def _make_fake():
    """绕过连库的 __init__，仅用于测试纯函数 align_columns。"""
    obj = object.__new__(_Fake)
    return obj


def test_align_drops_extra_columns():
    c = _make_fake()
    out = c.align_columns(c.fetch_by_date("20240101"))
    assert "extra_col" not in out.columns


def test_align_nan_to_none():
    c = _make_fake()
    out = c.align_columns(c.fetch_by_date("20240101"))
    assert out.iloc[0]["vol"] is None


def test_align_date_to_str():
    c = _make_fake()
    out = c.align_columns(c.fetch_by_date("20240101"))
    assert out.iloc[0]["trade_date"] == "20240101"


def test_align_fills_missing_columns():
    c = _make_fake()
    out = c.align_columns(pd.DataFrame([{"ts_code": "X.SZ", "trade_date": "20240101"}]))
    # schema 中存在但 df 缺失的列被补 None
    assert "open" in out.columns
    assert out.iloc[0]["open"] is None


def test_align_empty_df():
    c = _make_fake()
    assert c.align_columns(pd.DataFrame()).empty
