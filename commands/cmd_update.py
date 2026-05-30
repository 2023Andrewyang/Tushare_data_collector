# -*- coding: utf-8 -*-
"""update 命令：增量更新（日频逐日 + 低频检测）。"""
import logging

from config.settings import settings
from core.database import get_db_manager
from core.failure_handler import get_failure_handler
from collectors import COLLECTOR_REGISTRY
from commands import LOW_FREQ
from commands._common import print_summary
from scheduler.update_checker import UpdateChecker

logger = logging.getLogger(__name__)


def _date_range(args):
    """解析命令行参数得到 [start, end]。"""
    if args.date:
        return args.date, args.date
    if args.start or args.end:
        start = args.start or args.end
        end = args.end or args.start
        return start, end
    # 默认：最近交易日（取日历中最新交易日）
    db = get_db_manager()
    today = settings.data.get_end_date()
    last = db.get_max(settings.TBL_TRADE_CALENDAR, "cal_date",
                      "exchange='SSE' AND is_open=1 AND cal_date<=:t", {"t": today})
    last = last or today
    return last, last


def _run_low_freq(checker: UpdateChecker, first_day: str, only: str, results: dict):
    """在区间第一个交易日检测并执行低频采集器。"""
    def _maybe(name, should, full=True):
        if only and only != name:
            return
        if name not in COLLECTOR_REGISTRY:
            return
        if not should:
            logger.info(f"[{name}] 低频检测：无需更新，跳过")
            return
        Coll = COLLECTOR_REGISTRY[name]
        logger.info(f"[{name}] 低频检测：触发更新")
        if full:
            results[name] = Coll().run_full()
        else:
            results[name] = Coll().run_incremental(first_day)

    _maybe("trade_calendar", checker.should_update_trade_calendar(first_day))
    _maybe("stock_basic", checker.should_update_stock_basic())
    _maybe("dc_member", checker.should_update_dc_member(first_day))
    for tbl, name in ((settings.TBL_FINA_INDICATOR, "fina_indicator"),
                      (settings.TBL_FORECAST, "forecast"),
                      (settings.TBL_EXPRESS, "express")):
        _maybe(name, checker.should_update_financials(first_day, tbl), full=False)


def run(args):
    db = get_db_manager()
    checker = UpdateChecker()
    start, end = _date_range(args)
    only = args.collector

    # 确保 trade_calendar 当年存在（否则先补日历）
    if checker.should_update_trade_calendar(start):
        logger.info("trade_calendar 缺当年数据，先采集日历")
        COLLECTOR_REGISTRY["trade_calendar"]().run_full()

    # 取区间内交易日
    dates = db.fetch_all(
        f"SELECT cal_date FROM {settings.TBL_TRADE_CALENDAR} "
        f"WHERE exchange='SSE' AND is_open=1 AND cal_date>=:s AND cal_date<=:e "
        f"ORDER BY cal_date", {"s": start, "e": end})
    trade_dates = [r["cal_date"] for r in dates]

    if not trade_dates:
        logger.warning(f"区间 {start}~{end} 内无交易日，跳过日频采集")

    # 日频采集器：除低频外的全部
    if only:
        daily_names = [only] if only not in LOW_FREQ else []
    else:
        daily_names = [n for n in COLLECTOR_REGISTRY if n not in LOW_FREQ]

    results = {}
    for d in trade_dates:
        logger.info(f"=== update {d} ===")
        for name in daily_names:
            Coll = COLLECTOR_REGISTRY[name]
            r = Coll().run_incremental(d)
            prev = results.get(name, {"success": 0, "failed": 0})
            results[name] = {
                "success": prev.get("success", 0) + r.get("success", 0),
                "failed": prev.get("failed", 0) + r.get("failed", 0),
                "skipped": r.get("skipped", False),
            }

    # 低频检测：区间第一个交易日触发（无交易日则用 start）
    first_day = trade_dates[0] if trade_dates else start
    _run_low_freq(checker, first_day, only, results)

    print_summary(results)
    get_failure_handler().print_report()
