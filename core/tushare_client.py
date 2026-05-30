# -*- coding: utf-8 -*-
"""Tushare API 客户端：限频 + 重试 + 积分门控读取。

采集器统一通过 query(api_name, fields=..., **kwargs) 取数，不直接调用 self._pro。
同步串行调用 + 令牌桶限频，足以满足 5000 分限频，无需 asyncio。
"""
import logging
import threading
import time

import pandas as pd
import tushare as ts

from config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """令牌桶限频器（线程安全）。"""

    def __init__(self, rate: float, capacity: int = None):
        self.rate = rate
        self.capacity = capacity or max(1, int(rate))
        self.tokens = self.capacity
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, n: int = 1):
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return
            wait = (n - self.tokens) / self.rate
            self.tokens = 0
        time.sleep(wait)


class TushareClient:
    """Tushare Pro API 客户端（单例）。"""

    _instance = None
    _pro = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pro is None:
            self._init()

    def _init(self):
        token = settings.tushare.token
        if not token:
            raise ValueError("未配置 TUSHARE_TOKEN，请在 .env 中设置")
        ts.set_token(token)
        self._pro = ts.pro_api()
        self._limiter = RateLimiter(
            settings.tushare.requests_per_second,
            int(settings.tushare.requests_per_second * 2))
        logger.info("Tushare 客户端初始化成功")

    @property
    def points(self) -> int:
        return settings.tushare.points

    @property
    def pro(self):
        return self._pro

    def query(self, api_name: str, fields: str = None, **kwargs) -> pd.DataFrame:
        """通用取数。内置令牌桶限频 + 失败重试（指数退避）。"""
        last_exc = None
        delay = settings.tushare.retry_interval
        for attempt in range(settings.tushare.max_retries + 1):
            try:
                self._limiter.acquire()
                if fields:
                    df = self._pro.query(api_name, fields=fields, **kwargs)
                else:
                    df = self._pro.query(api_name, **kwargs)
                return df if df is not None else pd.DataFrame()
            except Exception as e:
                last_exc = e
                if attempt < settings.tushare.max_retries:
                    logger.warning(
                        f"[{api_name}] 调用失败"
                        f"({attempt + 1}/{settings.tushare.max_retries + 1}): {e}，"
                        f"{delay}s 后重试")
                    time.sleep(delay)
                    delay *= settings.tushare.retry_backoff
                else:
                    logger.error(f"[{api_name}] 最终失败: {e}")
        raise last_exc


def get_tushare_client() -> TushareClient:
    """获取 Tushare 客户端实例（单例）。"""
    return TushareClient()
