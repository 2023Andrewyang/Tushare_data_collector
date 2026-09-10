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
    with patch("core.tushare_client.TushareClient.query", return_value=fake):
        c = DailyQuoteCollector()
        r = c.run_incremental("20240102")
        assert r["success"] == 1
        r2 = c.run_incremental("20240102")
        assert r2["success"] == 0       # 幂等
    db.execute("DELETE FROM daily_quote WHERE ts_code='TEST.SZ'")


@pytest.mark.db
def test_skip_when_points_low(db, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings.tushare, "points", 0)
    from collectors.dc_index import DcIndexCollector
    r = DcIndexCollector().run_full("20240101", "20240105")
    assert r.get("skipped") is True


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
