# -*- coding: utf-8 -*-
"""采集器测试（mock client.query，需要 PG 写入）。"""
from unittest.mock import patch

import pandas as pd
import pytest

from collectors import COLLECTOR_REGISTRY, BASIC_COLLECTORS


def test_registry_complete():
    assert len(COLLECTOR_REGISTRY) == 21
    assert "stock_basic" in COLLECTOR_REGISTRY
    assert "trade_calendar" in COLLECTOR_REGISTRY
    assert BASIC_COLLECTORS == ["stock_basic", "trade_calendar"]


def test_all_collectors_have_required_attrs():
    for name, Coll in COLLECTOR_REGISTRY.items():
        assert Coll.TASK_NAME, f"{name} 缺 TASK_NAME"
        assert Coll.TABLE_NAME, f"{name} 缺 TABLE_NAME"
        assert isinstance(Coll.KEY_FIELDS, list) and Coll.KEY_FIELDS, f"{name} 缺 KEY_FIELDS"
        assert isinstance(Coll.REQUIRED_POINTS, int)


@pytest.mark.db
def test_daily_quote_save_idempotent(db):
    from collectors.daily_quote import DailyQuoteCollector
    fake = pd.DataFrame([{
        "ts_code": "TEST.SZ", "trade_date": "20240102",
        "open": 1, "high": 2, "low": 0.5, "close": 1.5,
        "pre_close": 1, "change": 0.5, "pct_chg": 50,
        "vol": 100, "amount": 150}])
    # 先清掉上一次运行留下的断点，否则本用例会被断点续传直接跳过
    # （第二次执行时 success 会是 0 而不是 1）。
    db.execute("DELETE FROM collection_checkpoint WHERE collector='daily_quote' "
               "AND item_type='date' AND item_key='20240102'")
    with patch("core.tushare_client.TushareClient.query", return_value=fake):
        c = DailyQuoteCollector()
        r = c.run_incremental("20240102")
        assert r["success"] == 1
        r2 = c.run_incremental("20240102")
        assert r2["success"] == 0       # 幂等
    db.execute("DELETE FROM daily_quote WHERE ts_code='TEST.SZ'")
    db.execute("DELETE FROM collection_checkpoint WHERE collector='daily_quote' "
               "AND item_type='date' AND item_key='20240102'")


@pytest.mark.db
def test_skip_when_points_low(db, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings.tushare, "points", 0)
    from collectors.dc_index import DcIndexCollector
    r = DcIndexCollector().run_full("20240101", "20240105")
    assert r.get("skipped") is True


class _FakeDB:
    """替身库：只回答 fina_indicator 降级补齐用到的两条查询。"""

    def __init__(self, codes, have=()):
        self.codes = list(codes)
        self.have = set(have)

    def fetch_all(self, sql, params=None):
        if "stock_basic" in sql:
            return [{"ts_code": c} for c in self.codes]
        if "fina_indicator" in sql:
            return [{"ts_code": c} for c in self.have]
        return []


def _fina_collector(client, db):
    """绕过 __init__ 构造采集器，避免单元测试连库/联网。"""
    from collectors.fina_indicator import FinaIndicatorCollector
    c = FinaIndicatorCollector.__new__(FinaIndicatorCollector)
    c.client = client
    c.db = db
    return c


def _fake_query_factory(calls, period_rows=None, period_error=None, by_code=None):
    def fake_query(api_name, fields=None, **kw):
        calls.append(kw)
        if "ts_code" in kw:
            return (by_code or {}).get(kw["ts_code"], pd.DataFrame())
        if period_error is not None:
            raise period_error
        return period_rows if period_rows is not None else pd.DataFrame()
    return fake_query


def test_fina_falls_back_to_by_stock_when_period_query_fails():
    """整期查询报 HTTP 400 时，自动按个股补齐缺失股票。"""
    from types import SimpleNamespace
    calls = []
    row = pd.DataFrame([{"ts_code": "A.SZ", "ann_date": "20230428",
                         "end_date": "20230331", "eps": 1.0}])
    client = SimpleNamespace(query=_fake_query_factory(
        calls, period_error=RuntimeError("HTTP 400"), by_code={"A.SZ": row}))
    c = _fina_collector(client, _FakeDB(("A.SZ", "B.SZ")))

    df = c.fetch_by_period("20230331")

    assert len(df) == 1 and df.iloc[0]["ts_code"] == "A.SZ"
    assert sum(1 for k in calls if "ts_code" in k) == 2   # 两只都查了


def test_fina_fallback_only_queries_stocks_missing_the_period():
    """已有该报告期的股票不再重复请求，保证重复运行快速收敛。"""
    from types import SimpleNamespace
    calls = []
    client = SimpleNamespace(query=_fake_query_factory(
        calls, period_error=RuntimeError("HTTP 400")))
    c = _fina_collector(client, _FakeDB(("A.SZ", "B.SZ", "C.SZ"), have=("A.SZ",)))

    c.fetch_by_period("20230331")

    assert sorted(k["ts_code"] for k in calls if "ts_code" in k) == ["B.SZ", "C.SZ"]


def test_fina_no_fallback_when_period_query_succeeds():
    """整期查询正常时不触发逐股补齐，避免无谓地打满全市场。"""
    from types import SimpleNamespace
    calls = []
    rows = pd.DataFrame([{"ts_code": "A.SZ", "ann_date": "20230428",
                          "end_date": "20230331", "eps": 1.0}])
    client = SimpleNamespace(query=_fake_query_factory(calls, period_rows=rows))
    c = _fina_collector(client, _FakeDB(("A.SZ", "B.SZ")))

    df = c.fetch_by_period("20230331")

    assert len(df) == 1
    assert sum(1 for k in calls if "ts_code" in k) == 0


def test_fina_skips_fallback_for_future_period():
    """未来报告期不可能有数据，直接跳过降级，不打全市场。"""
    from datetime import datetime
    from types import SimpleNamespace
    calls = []
    client = SimpleNamespace(query=_fake_query_factory(
        calls, period_error=RuntimeError("HTTP 400")))
    c = _fina_collector(client, _FakeDB(("A.SZ", "B.SZ")))

    df = c.fetch_by_period(f"{datetime.now().year + 1}0331")

    assert df.empty
    assert sum(1 for k in calls if "ts_code" in k) == 0


@pytest.mark.db
def test_checkpoint_skips_completed_and_resumes_interrupted_work(db, caplog):
    """成功日期不会重复请求；中断日期会在下次执行时恢复。"""
    import logging

    from collectors.daily_quote import DailyQuoteCollector

    completed_date = "20991230"
    interrupted_date = "20991231"

    def fake_quote(trade_date):
        return pd.DataFrame([{
            "ts_code": "CHECKPOINT.SZ", "trade_date": trade_date,
            "open": 1, "high": 2, "low": 0.5, "close": 1.5,
            "pre_close": 1, "change": 0.5, "pct_chg": 50,
            "vol": 100, "amount": 150,
        }])

    db.execute(
        "DELETE FROM collection_checkpoint WHERE collector='daily_quote' "
        "AND item_type='date' AND item_key IN (:completed, :interrupted)",
        {"completed": completed_date, "interrupted": interrupted_date})
    db.execute("DELETE FROM daily_quote WHERE ts_code='CHECKPOINT.SZ'")

    try:
        caplog.set_level(logging.INFO)
        with patch("core.tushare_client.TushareClient.query",
                   side_effect=lambda _, trade_date, **__: fake_quote(trade_date)) as query:
            collector = DailyQuoteCollector()
            first = collector.run_incremental(completed_date)
            second = collector.run_incremental(completed_date)

        assert first["failed"] == 0
        assert second["skipped"] is True
        assert query.call_count == 1
        assert "断点续传跳过" in caplog.text

        collector = DailyQuoteCollector()
        with patch("core.tushare_client.TushareClient.query",
                   side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                collector.run_incremental(interrupted_date)

        interrupted = db.fetch_one(
            "SELECT status FROM collection_checkpoint WHERE collector='daily_quote' "
            "AND item_type='date' AND item_key=:date", {"date": interrupted_date})
        assert interrupted["status"] == "interrupted"

        with patch("core.tushare_client.TushareClient.query",
                   side_effect=lambda _, trade_date, **__: fake_quote(trade_date)) as query:
            resumed = collector.run_incremental(interrupted_date)

        assert resumed["failed"] == 0
        assert query.call_count == 1
        recovered = db.fetch_one(
            "SELECT status FROM collection_checkpoint WHERE collector='daily_quote' "
            "AND item_type='date' AND item_key=:date", {"date": interrupted_date})
        assert recovered["status"] == "succeeded"
    finally:
        db.execute(
            "DELETE FROM collection_checkpoint WHERE collector='daily_quote' "
            "AND item_type='date' AND item_key IN (:completed, :interrupted)",
            {"completed": completed_date, "interrupted": interrupted_date})
        db.execute("DELETE FROM daily_quote WHERE ts_code='CHECKPOINT.SZ'")
