# -*- coding: utf-8 -*-
"""断点与数据缺口分析：对比交易日历与各行情表的实际覆盖日期。

用法:
  python scripts/diag_gap.py [表名 ...]
默认分析 daily_quote、daily_basic。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()
    tables = sys.argv[1:] or [
        settings.TBL_DAILY_QUOTE, settings.TBL_DAILY_BASIC,
        settings.TBL_ADJ_FACTOR, settings.TBL_STK_LIMIT, settings.TBL_INDEX_DAILY,
        settings.TBL_MONEYFLOW, settings.TBL_LIMIT_LIST, settings.TBL_SUSPEND,
        settings.TBL_STOCK_ST, settings.TBL_MARGIN_SUMMARY, settings.TBL_BLOCK_TRADE,
        settings.TBL_TOP_LIST, settings.TBL_MONEYFLOW_HSGT,
    ]

    print("=" * 90)
    print("A) trade_calendar 各交易所覆盖")
    rows = db.fetch_all(
        "SELECT exchange, count(*) AS c, "
        "sum(CASE WHEN is_open=1 THEN 1 ELSE 0 END) AS opendays, "
        "min(cal_date) AS mn, max(cal_date) AS mx "
        "FROM trade_calendar GROUP BY exchange ORDER BY exchange")
    for r in rows:
        print(f"  {r['exchange']:<6} 总天数={r['c']:<6} 交易日={r['opendays']:<6} "
              f"{r['mn']} ~ {r['mx']}")

    cal = db.fetch_all(
        "SELECT cal_date FROM trade_calendar WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date",
        {"s": settings.data.start_date, "e": settings.data.end_date or "20260910"})
    cal_dates = [r["cal_date"] for r in cal]
    print(f"  -> 采集区间 {settings.data.start_date}~{settings.data.end_date or 'today'} "
          f"内 SSE 交易日 = {len(cal_dates)}")

    print()
    print("=" * 90)
    print("B) checkpoint 明细（按 collector/item_type/status，含时间与尝试次数）")
    rows = db.fetch_all(
        "SELECT collector, item_type, status, count(*) AS c, "
        "min(item_key) AS mn, max(item_key) AS mx, "
        "min(started_at) AS first_start, max(updated_at) AS last_upd, "
        "max(attempt_count) AS max_att "
        "FROM collection_checkpoint GROUP BY collector, item_type, status "
        "ORDER BY collector, item_type, status")
    for r in rows:
        print(f"  {r['collector']:<16}{r['item_type']:<10}{r['status']:<13}"
              f"{r['c']:>7}  {r['mn']} ~ {r['mx']}  "
              f"last={r['last_upd']}  max_att={r['max_att']}")

    print()
    print("=" * 90)
    print("C) 各行情表 vs 交易日历 的缺口")
    for t in tables:
        try:
            r = db.fetch_one(f"SELECT count(*) AS c FROM {t}")
        except Exception as e:  # noqa: BLE001
            print(f"\n[{t}] 表不存在或读取失败: {e}")
            continue
        if r["c"] == 0:
            print(f"\n[{t}] 空表（0 行）")
            continue
        have = {x["trade_date"] for x in db.fetch_all(
            f"SELECT DISTINCT trade_date FROM {t}")}
        missing = [d for d in cal_dates if d not in have]
        extra = sorted(have - set(cal_dates))
        print(f"\n[{t}] 总行数={r['c']}  有数据交易日={len(have)}  "
              f"日历交易日={len(cal_dates)}  缺失={len(missing)}")
        if missing:
            print(f"  缺失日期({len(missing)}): {','.join(missing[:60])}"
                  f"{' ...' if len(missing) > 60 else ''}")
        if extra:
            print(f"  非交易日却有数据({len(extra)}): {','.join(extra[:20])}")
        # 每日行数分布，找出明显偏少的日期（可能采集不完整）
        rows = db.fetch_all(
            f"SELECT trade_date, count(*) AS c FROM {t} GROUP BY trade_date")
        counts = sorted((x["c"] for x in rows))
        if counts:
            med = counts[len(counts) // 2]
            thin = sorted(((x["trade_date"], x["c"]) for x in rows
                           if x["c"] < med * 0.5), key=lambda p: p[0])
            print(f"  每日行数中位数={med}  行数<中位数50% 的日期={len(thin)}")
            if thin:
                print("  偏薄日期(前30): " +
                      ", ".join(f"{d}:{c}" for d, c in thin[:30]))


if __name__ == "__main__":
    main()
