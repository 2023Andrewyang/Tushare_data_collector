# -*- coding: utf-8 -*-
"""表结构测试（单元，不连库）。"""
from models.schema import metadata, TABLES


def test_table_count():
    assert len(TABLES) >= 21


def test_key_tables_exist():
    for t in ("daily_quote", "limit_list", "stk_limit", "top_inst",
              "margin_summary", "fina_indicator", "task_failure_log"):
        assert t in TABLES


def test_stk_limit_vs_limit_list():
    # 涨跌停价格 vs 涨跌停列表，是两张不同的表（修复 D1）
    assert "stk_limit" in TABLES and "limit_list" in TABLES
    assert TABLES["stk_limit"] is not TABLES["limit_list"]


def test_margin_summary_primary_key():
    # 修复 D3：主键改 (trade_date, exchange_id)
    pk = [c.name for c in TABLES["margin_summary"].primary_key.columns]
    assert pk == ["trade_date", "exchange_id"]


def test_fina_indicator_primary_key():
    # 修复 D4：主键加 ann_date
    pk = set(c.name for c in TABLES["fina_indicator"].primary_key.columns)
    assert pk == {"ts_code", "ann_date", "end_date"}


def test_block_trade_primary_key():
    pk = set(c.name for c in TABLES["block_trade"].primary_key.columns)
    assert pk == {"ts_code", "trade_date", "price", "vol"}


def test_metadata_has_tables():
    assert len(metadata.tables) == len(TABLES)
