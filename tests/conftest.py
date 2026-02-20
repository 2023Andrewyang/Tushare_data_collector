# -*- coding: utf-8 -*-
"""
Pytest配置和共享fixtures
"""
import os
import sys
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def db_manager():
    """数据库管理器fixture"""
    from core.database import get_db_manager
    manager = get_db_manager()
    yield manager
    # 测试完成后不关闭连接，因为是单例模式


@pytest.fixture(scope="session")
def tushare_client():
    """Tushare客户端fixture"""
    from config.tushare_token import TUSHARE_TOKEN
    
    if TUSHARE_TOKEN == "your_tushare_token_here":
        pytest.skip("请先配置Tushare Token")
    
    from core.tushare_client import get_tushare_client
    client = get_tushare_client()
    yield client


@pytest.fixture(scope="session")
def task_manager():
    """任务管理器fixture"""
    from core.task_manager import get_task_manager
    return get_task_manager()


@pytest.fixture(scope="session")
def failure_handler():
    """失败处理器fixture"""
    from core.failure_handler import get_failure_handler
    return get_failure_handler()


@pytest.fixture
def test_trade_date():
    """测试用交易日期"""
    return "20240102"  # 2024年第一个交易日


@pytest.fixture
def test_stock_code():
    """测试用股票代码"""
    return "000001.SZ"  # 平安银行

