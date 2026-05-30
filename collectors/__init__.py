# -*- coding: utf-8 -*-
"""数据采集器模块 + 注册表。

新增采集器 = 写一个文件 + 在 COLLECTOR_REGISTRY 加一行。
命令层、status、retry 全部据此自动感知，无需改其他地方。
"""
from collectors.base_collector import (
    BaseCollector, DateBasedCollector, StockBasedCollector,
    PeriodBasedCollector, SnapshotCollector,
)
from collectors.stock_basic import StockBasicCollector
from collectors.trade_calendar import TradeCalendarCollector
from collectors.daily_quote import DailyQuoteCollector
from collectors.daily_basic import DailyBasicCollector
from collectors.index_daily import IndexDailyCollector
from collectors.adj_factor import AdjFactorCollector
from collectors.stk_limit import StkLimitCollector
from collectors.suspend import SuspendCollector
from collectors.stock_st import StockSTCollector
from collectors.moneyflow import MoneyflowCollector
from collectors.moneyflow_hsgt import MoneyflowHsgtCollector
from collectors.limit_list import LimitListCollector
from collectors.top_list import TopListCollector
from collectors.block_trade import BlockTradeCollector
from collectors.margin import MarginCollector
from collectors.fina_indicator import FinaIndicatorCollector
from collectors.forecast import ForecastCollector
from collectors.express import ExpressCollector
from collectors.dc_index import DcIndexCollector
from collectors.dc_daily import DcDailyCollector
from collectors.dc_member import DcMemberCollector

# 采集器注册表（命令层据此遍历）
COLLECTOR_REGISTRY = {
    "stock_basic":     StockBasicCollector,
    "trade_calendar":  TradeCalendarCollector,
    "daily_quote":     DailyQuoteCollector,
    "daily_basic":     DailyBasicCollector,
    "index_daily":     IndexDailyCollector,
    "adj_factor":      AdjFactorCollector,
    "stk_limit":       StkLimitCollector,
    "suspend":         SuspendCollector,
    "stock_st":        StockSTCollector,
    "moneyflow":       MoneyflowCollector,
    "moneyflow_hsgt":  MoneyflowHsgtCollector,
    "limit_list":      LimitListCollector,
    "top_list":        TopListCollector,
    "block_trade":     BlockTradeCollector,
    "margin":          MarginCollector,
    "fina_indicator":  FinaIndicatorCollector,
    "forecast":        ForecastCollector,
    "express":         ExpressCollector,
    "dc_index":        DcIndexCollector,
    "dc_daily":        DcDailyCollector,
    "dc_member":       DcMemberCollector,
}

# 执行顺序分组：基础采集器必须最先（后续按交易日循环依赖日历/股票列表）
BASIC_COLLECTORS = ["stock_basic", "trade_calendar"]

__all__ = [
    "BaseCollector", "DateBasedCollector", "StockBasedCollector",
    "PeriodBasedCollector", "SnapshotCollector",
    "COLLECTOR_REGISTRY", "BASIC_COLLECTORS",
]
