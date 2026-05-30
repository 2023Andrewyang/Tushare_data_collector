# -*- coding: utf-8 -*-
"""status 命令：查看数据状态 / 失败汇总 / 当日覆盖。"""
import logging

from config.settings import settings
from core.database import get_db_manager
from core.failure_handler import get_failure_handler
from collectors import COLLECTOR_REGISTRY

logger = logging.getLogger(__name__)

# 当日各接口期望阈值（低于则标记 ⚠️）
EXPECT = {
    "daily_quote": 5000, "daily_basic": 5000, "moneyflow": 4000,
    "moneyflow_hsgt": 1, "index_daily": 1, "dc_sector_daily": 100,
}

# 采集器名 -> 表名（用于按表统计）
_TABLE_BY_NAME = {
    "stock_basic": settings.TBL_STOCK_BASIC,
    "trade_calendar": settings.TBL_TRADE_CALENDAR,
    "daily_quote": settings.TBL_DAILY_QUOTE,
    "daily_basic": settings.TBL_DAILY_BASIC,
    "index_daily": settings.TBL_INDEX_DAILY,
    "adj_factor": settings.TBL_ADJ_FACTOR,
    "stk_limit": settings.TBL_STK_LIMIT,
    "suspend": settings.TBL_SUSPEND,
    "stock_st": settings.TBL_STOCK_ST,
    "moneyflow": settings.TBL_MONEYFLOW,
    "moneyflow_hsgt": settings.TBL_MONEYFLOW_HSGT,
    "limit_list": settings.TBL_LIMIT_LIST,
    "top_list": settings.TBL_TOP_LIST,
    "top_inst": settings.TBL_TOP_INST,
    "block_trade": settings.TBL_BLOCK_TRADE,
    "margin": settings.TBL_MARGIN_SUMMARY,
    "fina_indicator": settings.TBL_FINA_INDICATOR,
    "forecast": settings.TBL_FORECAST,
    "express": settings.TBL_EXPRESS,
    "dc_index": settings.TBL_DC_SECTOR_DAILY,
    "dc_daily": settings.TBL_DC_SECTOR_KLINE,
    "dc_member": settings.TBL_DC_SECTOR_MEMBER,
}


def _date_col(table: str) -> str:
    """该表用于取"最新日期"的列。"""
    if table in (settings.TBL_FINA_INDICATOR, settings.TBL_FORECAST,
                 settings.TBL_EXPRESS):
        return "end_date"
    if table == settings.TBL_TRADE_CALENDAR:
        return "cal_date"
    if table == settings.TBL_DC_SECTOR_MEMBER:
        return "snapshot_date"
    if table == settings.TBL_STOCK_BASIC:
        return None
    return "trade_date"


def run(args):
    db = get_db_manager()
    fh = get_failure_handler()

    if getattr(args, "failures", False):
        fh.print_report()
        return

    if args.date:
        _status_by_date(db, args.date)
        return

    _status_overall(db)


def _status_overall(db):
    print("\n" + "=" * 64)
    print(f"{'表名':<22}{'行数':>14}{'最新日期':>16}")
    print("-" * 64)
    for name, table in _TABLE_BY_NAME.items():
        try:
            cnt = db.count(table)
            col = _date_col(table)
            latest = db.get_max(table, col) if col else "-"
        except Exception as e:
            cnt, latest = "ERR", str(e)[:20]
        print(f"{table:<22}{str(cnt):>14}{str(latest):>16}")
    print("=" * 64)


def _status_by_date(db, date: str):
    print("\n" + "=" * 56)
    print(f"日期 {date} 各接口记录数")
    print("-" * 56)
    for name in COLLECTOR_REGISTRY:
        table = _TABLE_BY_NAME.get(name)
        if not table:
            continue
        col = _date_col(table)
        if col is None:
            continue
        try:
            cnt = db.count(table, f"{col}=:d", {"d": date})
        except Exception as e:
            print(f"{name:<20}{'ERR':>10}  {str(e)[:20]}")
            continue
        flag = ""
        if name in EXPECT and cnt < EXPECT[name]:
            flag = "  ⚠️ 低于阈值"
        print(f"{name:<20}{cnt:>10}{flag}")
    print("=" * 56)
