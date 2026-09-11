# -*- coding: utf-8 -*-
"""全量缺口核对：逐个采集器对比「应有日期」与「表内实际日期」，列出缺失清单。

用法:
  python scripts/gap_report.py
  python scripts/gap_report.py --show-missing 60
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings          # noqa: E402
from core.database import get_db_manager      # noqa: E402

db = get_db_manager()

# 采集器 -> (表名, 日期列, 类型)
SPEC = {
    "stock_basic":    (settings.TBL_STOCK_BASIC, None, "snapshot"),
    "trade_calendar": (settings.TBL_TRADE_CALENDAR, "cal_date", "skip"),
    "daily_quote":    (settings.TBL_DAILY_QUOTE, "trade_date", "date"),
    "daily_basic":    (settings.TBL_DAILY_BASIC, "trade_date", "date"),
    "index_daily":    (settings.TBL_INDEX_DAILY, "trade_date", "date"),
    "adj_factor":     (settings.TBL_ADJ_FACTOR, "trade_date", "date"),
    "stk_limit":      (settings.TBL_STK_LIMIT, "trade_date", "date"),
    "suspend":        (settings.TBL_SUSPEND, "trade_date", "date"),
    "stock_st":       (settings.TBL_STOCK_ST, "trade_date", "date"),
    "moneyflow":      (settings.TBL_MONEYFLOW, "trade_date", "date"),
    "moneyflow_hsgt": (settings.TBL_MONEYFLOW_HSGT, "trade_date", "date"),
    "limit_list":     (settings.TBL_LIMIT_LIST, "trade_date", "date"),
    "top_list":       (settings.TBL_TOP_LIST, "trade_date", "date"),
    "top_inst":       (settings.TBL_TOP_INST, "trade_date", "date"),
    "block_trade":    (settings.TBL_BLOCK_TRADE, "trade_date", "date"),
    "margin":         (settings.TBL_MARGIN_SUMMARY, "trade_date", "date"),
    "fina_indicator": (settings.TBL_FINA_INDICATOR, "end_date", "period"),
    "forecast":       (settings.TBL_FORECAST, "end_date", "period"),
    "express":        (settings.TBL_EXPRESS, "end_date", "period"),
    "dc_index":       (settings.TBL_DC_SECTOR_DAILY, "trade_date", "date"),
    "dc_daily":       (settings.TBL_DC_SECTOR_KLINE, "trade_date", "date"),
    "dc_member":      (settings.TBL_DC_SECTOR_MEMBER, "snapshot_date", "snapshot"),
}


def trade_dates(start, end):
    return [r["cal_date"] for r in db.fetch_all(
        f"SELECT cal_date FROM {settings.TBL_TRADE_CALENDAR} "
        f"WHERE exchange='SSE' AND is_open=1 AND cal_date>=:s AND cal_date<=:e "
        f"ORDER BY cal_date", {"s": start, "e": end})]


def gen_periods(start, end):
    sy, ey = int(start[:4]), int(end[:4])
    out = []
    for y in range(sy, ey + 1):
        for q in ("0331", "0630", "0930", "1231"):
            p = f"{y}{q}"
            if start <= p <= end:
                out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-missing", type=int, default=25,
                    help="每个采集器最多展示多少个缺失项")
    args = ap.parse_args()

    start = settings.data.start_date
    end = settings.data.get_end_date()
    cal = trade_dates(start, end)
    periods = gen_periods(start, end)

    print("=" * 96)
    print(f"全量缺口核对  范围 {start} ~ {end}   交易日 {len(cal)} 天   报告期 {len(periods)} 个")
    print("=" * 96)
    print(f"{'采集器':<17}{'表名':<20}{'应有':>7}{'实际':>7}{'缺失':>7}   状态")
    print("-" * 96)

    problems = []
    for name, (table, col, kind) in SPEC.items():
        if kind == "skip":
            continue
        try:
            total_rows = db.count(table)
        except Exception as e:
            print(f"{name:<17}{table:<20}{'ERR':>7}{'':>7}{'':>7}   {str(e)[:30]}")
            continue
        if kind == "snapshot":
            print(f"{name:<17}{table:<20}{'-':>7}{total_rows:>7}{'-':>7}   快照表")
            continue

        expected = periods if kind == "period" else cal
        got = {r["d"] for r in db.fetch_all(
            f"SELECT DISTINCT {col} AS d FROM {table} "
            f"WHERE {col}>=:s AND {col}<=:e", {"s": start, "e": end})}
        missing = [d for d in expected if d not in got]
        status = "完整 ✅" if not missing else f"缺 {len(missing)} 项 ❌"
        print(f"{name:<17}{table:<20}{len(expected):>7}{len(got):>7}{len(missing):>7}   {status}")
        if missing:
            problems.append((name, missing))
            head = missing[:args.show_missing]
            for i in range(0, len(head), 10):
                print("      " + " ".join(head[i:i + 10]))
            if len(missing) > len(head):
                print(f"      ... 其余 {len(missing) - len(head)} 项省略")

    print("-" * 96)
    pend = db.fetch_all(
        f"SELECT collector, error_type, COUNT(*) AS c FROM {settings.TBL_TASK_FAILURE_LOG} "
        f"WHERE status='pending' GROUP BY collector, error_type ORDER BY c DESC")
    print("失败日志待处理（按采集器/类型）:")
    if not pend:
        print("  无")
    for r in pend:
        print(f"  {r['collector']:<18} {r['error_type']:<16} {r['c']}")
    print("=" * 96)
    if not problems:
        print("结论：所有采集器均无缺口 ✅")
    else:
        print(f"结论：仍有 {len(problems)} 个采集器存在缺口："
              + ", ".join(f"{n}({len(m)})" for n, m in problems))


if __name__ == "__main__":
    main()
