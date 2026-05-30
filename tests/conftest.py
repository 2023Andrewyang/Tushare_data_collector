# -*- coding: utf-8 -*-
"""Pytest 配置与共享 fixtures。

测试分三层：
- 单元测试（默认跑）：不连库、不联网。
- db 测试（@pytest.mark.db）：需要本地 PostgreSQL。
- integration 测试（@pytest.mark.integration）：需要 Tushare token + 联网，默认跳过。
"""
import os
import sys

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    config.addinivalue_line("markers", "db: 需要本地 PostgreSQL")
    config.addinivalue_line("markers", "integration: 需要 Tushare token + 联网")


@pytest.fixture(scope="session")
def db():
    """数据库 fixture：建表，结束时清理测试数据。PG 不可用则跳过。"""
    from core.database import get_db_manager
    try:
        m = get_db_manager()
    except Exception as e:
        pytest.skip(f"PostgreSQL 不可用: {e}")
    if not m.healthcheck():
        pytest.skip("PostgreSQL 不可用")
    m.create_all_tables()
    yield m
    # 清理测试数据
    try:
        m.execute("DELETE FROM daily_quote WHERE ts_code LIKE 'TEST%'")
        m.execute("DELETE FROM daily_quote WHERE ts_code = 'T.SZ'")
        m.execute("DELETE FROM task_failure_log WHERE collector LIKE 'test_%'")
    except Exception:
        pass


@pytest.fixture(scope="session")
def tushare_client():
    """Tushare 客户端 fixture（integration 用）。"""
    from config.settings import settings
    if not settings.tushare.token:
        pytest.skip("未配置 Tushare Token")
    from core.tushare_client import get_tushare_client
    return get_tushare_client()


@pytest.fixture
def test_trade_date():
    return "20240102"


@pytest.fixture
def test_stock_code():
    return "000001.SZ"
