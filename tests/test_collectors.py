# -*- coding: utf-8 -*-
"""
采集器测试
"""
import pytest
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.tushare_token import TUSHARE_TOKEN


# 跳过条件：未配置Token
skip_no_token = pytest.mark.skipif(
    TUSHARE_TOKEN == "your_tushare_token_here",
    reason="请先配置Tushare Token"
)


@skip_no_token
class TestStockListCollector:
    """股票列表采集器测试"""
    
    def test_collect_full(self):
        """测试全量采集"""
        from collectors.stock_list import StockListCollector
        
        collector = StockListCollector()
        result = collector.collect_full()
        
        assert result is not None
        assert result.get("success", 0) > 0 or result.get("total_records", 0) > 0
    
    def test_get_stock_count(self, db_manager):
        """测试获取股票数量统计"""
        from collectors.stock_list import StockListCollector
        
        # 先确保有数据
        count = db_manager.count("stock_list")
        if count == 0:
            pytest.skip("股票列表为空，请先运行全量同步")
        
        collector = StockListCollector()
        stats = collector.get_stock_count()
        
        assert isinstance(stats, dict)


@skip_no_token
class TestTradeCalendarCollector:
    """交易日历采集器测试"""
    
    def test_collect_full(self):
        """测试全量采集"""
        from collectors.trade_calendar import TradeCalendarCollector
        
        collector = TradeCalendarCollector()
        result = collector.collect_full(
            start_date="20240101",
            end_date="20241231"
        )
        
        assert result is not None
        assert result.get("success", 0) >= 0
    
    def test_get_trade_dates(self, db_manager):
        """测试获取交易日列表"""
        from collectors.trade_calendar import TradeCalendarCollector
        
        # 检查是否有数据
        count = db_manager.count("trade_calendar")
        if count == 0:
            pytest.skip("交易日历为空，请先运行全量同步")
        
        collector = TradeCalendarCollector()
        dates = collector.get_trade_dates("20240101", "20240131")
        
        assert isinstance(dates, list)
        # 一月份应该有15-23个交易日
        assert 10 <= len(dates) <= 25
    
    def test_is_trade_date(self, db_manager):
        """测试判断交易日"""
        from collectors.trade_calendar import TradeCalendarCollector
        
        count = db_manager.count("trade_calendar")
        if count == 0:
            pytest.skip("交易日历为空")
        
        collector = TradeCalendarCollector()
        
        # 2024年1月1日是元旦，不是交易日
        assert not collector.is_trade_date("20240101")
        
        # 2024年1月2日是交易日
        assert collector.is_trade_date("20240102")


@skip_no_token
class TestDailyQuoteCollector:
    """日K线采集器测试"""
    
    def test_fetch_by_date(self):
        """测试按日期获取"""
        from collectors.daily_quote import DailyQuoteCollector
        
        collector = DailyQuoteCollector()
        df = collector.fetch_by_date("20240102")
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "ts_code" in df.columns
            assert "close" in df.columns
    
    def test_collect_by_stock(self):
        """测试按股票采集"""
        from collectors.daily_quote import DailyQuoteCollector
        
        collector = DailyQuoteCollector()
        result = collector.collect_by_stock(
            ts_code="000001.SZ",
            start_date="20240101",
            end_date="20240110"
        )
        
        assert result is not None
        assert "success" in result


@skip_no_token
class TestAdjFactorCollector:
    """复权因子采集器测试"""
    
    def test_fetch_by_date(self):
        """测试按日期获取"""
        from collectors.adj_factor import AdjFactorCollector
        
        collector = AdjFactorCollector()
        df = collector.fetch_by_date("20240102")
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "ts_code" in df.columns
            assert "adj_factor" in df.columns
    
    def test_get_adj_factor(self, db_manager):
        """测试获取单个复权因子"""
        from collectors.adj_factor import AdjFactorCollector
        
        count = db_manager.count("adj_factor")
        if count == 0:
            pytest.skip("复权因子数据为空")
        
        collector = AdjFactorCollector()
        factor = collector.get_adj_factor("000001.SZ")
        
        # 可能为None（没有数据）或float
        assert factor is None or isinstance(factor, (int, float))


@skip_no_token
class TestDailyBasicCollector:
    """每日指标采集器测试"""
    
    def test_fetch_by_date(self):
        """测试按日期获取"""
        from collectors.daily_basic import DailyBasicCollector
        
        collector = DailyBasicCollector()
        df = collector.fetch_by_date("20240102")
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "ts_code" in df.columns
            assert "total_mv" in df.columns
    
    def test_get_market_cap(self, db_manager):
        """测试获取市值"""
        from collectors.daily_basic import DailyBasicCollector
        
        count = db_manager.count("daily_basic")
        if count == 0:
            pytest.skip("每日指标数据为空")
        
        collector = DailyBasicCollector()
        cap = collector.get_market_cap("000001.SZ")
        
        # 可能为None或dict
        assert cap is None or isinstance(cap, dict)


@skip_no_token
class TestLimitPriceCollector:
    """涨跌停价格采集器测试"""
    
    def test_fetch_by_date(self):
        """测试按日期获取"""
        from collectors.limit_price import LimitPriceCollector
        
        collector = LimitPriceCollector()
        df = collector.fetch_by_date("20240102")
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "ts_code" in df.columns
            assert "up_limit" in df.columns
            assert "down_limit" in df.columns


@skip_no_token
class TestFinaIndicatorCollector:
    """财务指标采集器测试"""
    
    def test_generate_report_periods(self):
        """测试报告期生成"""
        from collectors.fina_indicator import FinaIndicatorCollector
        
        collector = FinaIndicatorCollector()
        periods = collector._generate_report_periods("20230101", "20231231")
        
        assert isinstance(periods, list)
        assert len(periods) == 4  # 2023年4个季度
        assert "20230331" in periods
        assert "20230630" in periods
        assert "20230930" in periods
        assert "20231231" in periods
    
    def test_fetch_by_period(self):
        """测试按报告期获取"""
        from collectors.fina_indicator import FinaIndicatorCollector
        
        collector = FinaIndicatorCollector()
        df = collector._fetch_by_period("20230930")
        
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "ts_code" in df.columns
            assert "end_date" in df.columns
            assert "roe" in df.columns
    
    def test_collect_by_stock(self):
        """测试按股票采集"""
        from collectors.fina_indicator import FinaIndicatorCollector
        
        collector = FinaIndicatorCollector()
        result = collector.collect_by_stock(
            ts_code="000001.SZ",
            start_date="20230101",
            end_date="20231231"
        )
        
        assert result is not None
        assert "success" in result


class TestBaseCollector:
    """基类功能测试"""
    
    def test_get_today(self):
        """测试获取今天日期"""
        from collectors.base_collector import BaseCollector
        from collectors.daily_quote import DailyQuoteCollector
        from datetime import datetime
        
        collector = DailyQuoteCollector()
        today = collector.get_today()
        
        assert len(today) == 8
        assert today == datetime.now().strftime("%Y%m%d")

