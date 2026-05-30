# -*- coding: utf-8 -*-
"""Tushare 客户端测试。"""
import time

import pytest

from core.tushare_client import RateLimiter


def test_rate_limiter_allows_burst():
    rl = RateLimiter(rate=100, capacity=5)
    t0 = time.monotonic()
    for _ in range(5):
        rl.acquire()
    # 桶内有 5 个令牌，5 次 acquire 应几乎不等待
    assert time.monotonic() - t0 < 0.5


def test_rate_limiter_throttles():
    rl = RateLimiter(rate=10, capacity=1)
    rl.acquire()           # 用掉唯一令牌
    t0 = time.monotonic()
    rl.acquire()           # 需等待约 0.1s 补充
    assert time.monotonic() - t0 >= 0.05


@pytest.mark.integration
def test_query_trade_cal(tushare_client):
    df = tushare_client.query("trade_cal", exchange="SSE",
                              start_date="20240101", end_date="20240110",
                              fields="exchange,cal_date,is_open,pretrade_date")
    assert not df.empty
    assert isinstance(tushare_client.points, int)
