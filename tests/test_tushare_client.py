# -*- coding: utf-8 -*-
"""
Tushare客户端测试
"""
import pytest
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTushareClient:
    """Tushare客户端测试"""
    
    def test_client_initialization(self, tushare_client):
        """测试客户端初始化"""
        assert tushare_client is not None
        assert tushare_client.pro is not None
    
    def test_get_stock_list(self, tushare_client):
        """测试获取股票列表"""
        df = tushare_client.get_stock_list(list_status='L')
        
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'ts_code' in df.columns
        assert 'name' in df.columns
        
        # 验证数据合理性
        assert len(df) > 1000  # 上市股票应该有几千只
    
    def test_get_trade_calendar(self, tushare_client):
        """测试获取交易日历"""
        df = tushare_client.get_trade_calendar(
            exchange="SSE",
            start_date="20240101",
            end_date="20240131"
        )
        
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'cal_date' in df.columns
        assert 'is_open' in df.columns
    
    def test_get_daily_quote(self, tushare_client, test_trade_date):
        """测试获取日线行情"""
        df = tushare_client.get_daily_quote(trade_date=test_trade_date)
        
        assert isinstance(df, pd.DataFrame)
        # 交易日应该有数据
        if not df.empty:
            assert 'ts_code' in df.columns
            assert 'trade_date' in df.columns
            assert 'close' in df.columns
    
    def test_get_daily_quote_by_stock(self, tushare_client, test_stock_code):
        """测试按股票获取日线行情"""
        df = tushare_client.get_daily_quote(
            ts_code=test_stock_code,
            start_date="20240101",
            end_date="20240131"
        )
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert all(df['ts_code'] == test_stock_code)
    
    def test_get_adj_factor(self, tushare_client, test_trade_date):
        """测试获取复权因子"""
        df = tushare_client.get_adj_factor(trade_date=test_trade_date)
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'ts_code' in df.columns
            assert 'adj_factor' in df.columns
    
    def test_get_daily_basic(self, tushare_client, test_trade_date):
        """测试获取每日指标"""
        df = tushare_client.get_daily_basic(trade_date=test_trade_date)
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'ts_code' in df.columns
            assert 'pe' in df.columns or 'pe_ttm' in df.columns
            assert 'total_mv' in df.columns
    
    def test_get_stk_limit(self, tushare_client, test_trade_date):
        """测试获取涨跌停价格"""
        df = tushare_client.get_stk_limit(trade_date=test_trade_date)
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'ts_code' in df.columns
            assert 'up_limit' in df.columns
            assert 'down_limit' in df.columns


class TestRateLimiter:
    """速率限制器测试"""
    
    def test_rate_limiter_basic(self):
        """测试基本速率限制"""
        from core.tushare_client import RateLimiter
        
        limiter = RateLimiter(rate=10.0, capacity=10)
        
        # 第一次获取应该立即成功
        wait_time = limiter.acquire(1)
        assert wait_time == 0.0
    
    def test_rate_limiter_burst(self):
        """测试突发请求"""
        from core.tushare_client import RateLimiter
        
        limiter = RateLimiter(rate=10.0, capacity=5)
        
        # 消耗所有令牌
        for _ in range(5):
            limiter.acquire(1)
        
        # 下一次应该需要等待
        wait_time = limiter.acquire(1)
        assert wait_time > 0


class TestTushareSingleton:
    """测试单例模式"""
    
    def test_singleton(self, tushare_client):
        """测试单例模式"""
        from core.tushare_client import get_tushare_client
        
        client1 = get_tushare_client()
        client2 = get_tushare_client()
        
        assert client1 is client2

