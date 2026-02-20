# -*- coding: utf-8 -*-
"""
Tushare API客户端封装模块
包含速率限制和并发控制
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from functools import wraps
from datetime import datetime
import threading

import tushare as ts
import pandas as pd

from config.settings import settings
from config.tushare_token import TUSHARE_TOKEN

logger = logging.getLogger(__name__)


class RateLimiter:
    """令牌桶速率限制器"""
    
    def __init__(self, rate: float, capacity: int = None):
        """
        Args:
            rate: 每秒生成的令牌数
            capacity: 桶的容量，默认等于rate
        """
        self.rate = rate
        self.capacity = capacity or int(rate)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> float:
        """获取令牌，返回需要等待的时间"""
        with self._lock:
            now = time.monotonic()
            # 补充令牌
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            else:
                # 计算需要等待的时间
                wait_time = (tokens - self.tokens) / self.rate
                self.tokens = 0
                return wait_time
    
    async def acquire_async(self, tokens: int = 1):
        """异步获取令牌"""
        wait_time = self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)


class TushareClient:
    """Tushare API客户端"""
    
    _instance = None
    _pro = None
    _rate_limiter = None
    _semaphore = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pro is None:
            self._initialize()
    
    def _initialize(self):
        """初始化客户端"""
        if TUSHARE_TOKEN == "your_tushare_token_here":
            raise ValueError("请先在 config/tushare_token.py 中配置您的Tushare Token")
        
        ts.set_token(TUSHARE_TOKEN)
        self._pro = ts.pro_api()
        
        # 初始化速率限制器
        self._rate_limiter = RateLimiter(
            rate=settings.tushare.requests_per_second,
            capacity=int(settings.tushare.requests_per_second * 2)
        )
        
        # 初始化并发信号量
        self._semaphore = asyncio.Semaphore(settings.tushare.max_concurrent)
        
        logger.info("Tushare客户端初始化成功")
    
    @property
    def pro(self):
        """获取Tushare Pro API实例"""
        return self._pro
    
    def _retry_decorator(func):
        """重试装饰器"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            delay = settings.tushare.retry_delay
            
            for attempt in range(settings.tushare.max_retries + 1):
                try:
                    # 等待速率限制
                    wait_time = self._rate_limiter.acquire()
                    if wait_time > 0:
                        time.sleep(wait_time)
                    
                    return func(self, *args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    if attempt < settings.tushare.max_retries:
                        logger.warning(
                            f"API调用失败 (尝试 {attempt + 1}/{settings.tushare.max_retries + 1}): {e}"
                        )
                        time.sleep(delay)
                        delay *= settings.tushare.retry_backoff
                    else:
                        logger.error(f"API调用最终失败: {e}")
            
            raise last_exception
        return wrapper
    
    @_retry_decorator
    def query(self, api_name: str, **kwargs) -> pd.DataFrame:
        """
        通用API查询方法
        
        Args:
            api_name: API名称
            **kwargs: API参数
            
        Returns:
            查询结果DataFrame
        """
        logger.debug(f"调用API: {api_name}, 参数: {kwargs}")
        df = self._pro.query(api_name, **kwargs)
        
        if df is None:
            return pd.DataFrame()
        
        logger.debug(f"API {api_name} 返回 {len(df)} 条记录")
        return df
    
    # ==================== 股票基础数据 ====================
    
    def get_stock_list(self, list_status: str = None) -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            list_status: L-上市, D-退市, P-暂停上市, None-全部
        """
        fields = "ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs"
        
        if list_status:
            return self.query('stock_basic', list_status=list_status, fields=fields)
        
        # 获取全部状态的股票
        dfs = []
        for status in ['L', 'D', 'P']:
            df = self.query('stock_basic', list_status=status, fields=fields)
            if not df.empty:
                dfs.append(df)
        
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    def get_trade_calendar(self, exchange: str = "SSE", 
                           start_date: str = None, 
                           end_date: str = None) -> pd.DataFrame:
        """
        获取交易日历
        
        Args:
            exchange: 交易所 SSE-上交所, SZSE-深交所, BSE-北交所
            start_date: 开始日期
            end_date: 结束日期
        """
        return self.query(
            'trade_cal',
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            fields="exchange,cal_date,is_open,pretrade_date"
        )
    
    # ==================== 行情数据 ====================
    
    def get_daily_quote(self, ts_code: str = None, trade_date: str = None,
                        start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取日线行情
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期（获取某天全市场数据）
            start_date: 开始日期
            end_date: 结束日期
        """
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        if trade_date:
            params['trade_date'] = trade_date
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self.query(
            'daily',
            **params,
            fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
        )
    
    def get_adj_factor(self, ts_code: str = None, trade_date: str = None,
                       start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取复权因子
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
        """
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        if trade_date:
            params['trade_date'] = trade_date
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self.query('adj_factor', **params)
    
    def get_daily_basic(self, ts_code: str = None, trade_date: str = None,
                        start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取每日指标（PE、市值等）
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期  
            end_date: 结束日期
        """
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        if trade_date:
            params['trade_date'] = trade_date
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        fields = "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv"
        
        return self.query('daily_basic', **params, fields=fields)
    
    def get_stk_limit(self, ts_code: str = None, trade_date: str = None,
                      start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取涨跌停价格
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
        """
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        if trade_date:
            params['trade_date'] = trade_date
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self.query(
            'stk_limit',
            **params,
            fields="ts_code,trade_date,pre_close,up_limit,down_limit"
        )
    
    def get_suspend(self, ts_code: str = None, trade_date: str = None,
                    start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取停复牌信息
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
        """
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        if trade_date:
            params['trade_date'] = trade_date
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self.query('suspend_d', **params)
    
    # ==================== 异步方法 ====================
    
    async def query_async(self, api_name: str, **kwargs) -> pd.DataFrame:
        """异步查询方法"""
        async with self._semaphore:
            await self._rate_limiter.acquire_async()
            
            # 在线程池中执行同步API调用
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.query(api_name, **kwargs)
            )


# 便捷函数
def get_tushare_client() -> TushareClient:
    """获取Tushare客户端实例"""
    return TushareClient()

