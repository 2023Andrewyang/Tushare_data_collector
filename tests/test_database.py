# -*- coding: utf-8 -*-
"""PostgreSQL 数据库管理器测试（需要本地 PG）。"""
import pytest


def test_singleton():
    from core.database import get_db_manager
    # 不触发连接也应是同一类的单例语义
    assert get_db_manager().__class__ is get_db_manager().__class__


@pytest.mark.db
def test_healthcheck(db):
    assert db.healthcheck()


@pytest.mark.db
def test_idempotent_upsert(db):
    rows = [{"ts_code": "T.SZ", "trade_date": "20200101", "close": 1.0},
            {"ts_code": "T.SZ", "trade_date": "20200101", "close": 1.0}]
    r1 = db.bulk_upsert("daily_quote", rows, ["ts_code", "trade_date"])
    r2 = db.bulk_upsert("daily_quote", rows, ["ts_code", "trade_date"])
    assert r1["affected"] == 1     # 两条同主键，只写入 1 条
    assert r2["affected"] == 0     # 再写一次全冲突，新增 0 条
    assert db.count("daily_quote", "ts_code=:c", {"c": "T.SZ"}) == 1
    db.execute("DELETE FROM daily_quote WHERE ts_code=:c", {"c": "T.SZ"})


@pytest.mark.db
def test_update_on_conflict(db):
    db.bulk_upsert("daily_quote",
                   [{"ts_code": "T.SZ", "trade_date": "20200102", "close": 1.0}],
                   ["ts_code", "trade_date"])
    db.bulk_upsert("daily_quote",
                   [{"ts_code": "T.SZ", "trade_date": "20200102", "close": 9.9}],
                   ["ts_code", "trade_date"], update_on_conflict=True)
    row = db.fetch_one("SELECT close FROM daily_quote "
                       "WHERE ts_code=:c AND trade_date='20200102'", {"c": "T.SZ"})
    assert float(row["close"]) == 9.9
    db.execute("DELETE FROM daily_quote WHERE ts_code=:c", {"c": "T.SZ"})


@pytest.mark.db
def test_fetch_helpers(db):
    db.bulk_upsert("daily_quote",
                   [{"ts_code": "T.SZ", "trade_date": "20200103", "close": 5.0}],
                   ["ts_code", "trade_date"])
    assert db.count("daily_quote", "ts_code=:c", {"c": "T.SZ"}) == 1
    assert db.get_max("daily_quote", "trade_date", "ts_code=:c", {"c": "T.SZ"}) == "20200103"
    one = db.fetch_one("SELECT * FROM daily_quote WHERE ts_code=:c", {"c": "T.SZ"})
    assert one["ts_code"] == "T.SZ"
    db.execute("DELETE FROM daily_quote WHERE ts_code=:c", {"c": "T.SZ"})
