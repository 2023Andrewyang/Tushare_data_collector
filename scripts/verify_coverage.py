# -*- coding: utf-8 -*-
"""覆盖度校验：逐表核对行数、交易日覆盖、缺失交易日与断点/失败状态。

用于判断「除了 daily_basic / daily_quote，其余表是否已采集完整」。

用法:
  python scripts/verify_coverage.py            # 全表核对
  python scripts/verify_coverage.py --missing  # 额外列出未覆盖交易日（最多每表 20 个）
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.database import get_db_manager  # noqa: E402

# 目标表：collector -> 表名（daily_basic / daily_quote 不在任务范围内）
TARGETS = [
    ("stock_basic", settings.TBL_STOCK_BASIC),
    ("trade_calendar", settings.TBL_TRADE_CALENDAR),
    ("index_daily", settings.TBL_INDEX_DAILY),
    ("adj_factor", settings.TBL_ADJ_FACTOR),
    ("stk_limit", settings.TBL_STK_LIMIT),
    ("suspend", settings.TBL_SUSPEND),
    ("stock_st", settings.TBL_STOCK_ST),
    ("moneyflow", settings.TBL_MONEYFLOW),
    ("moneyflow_hsgt", settings.TBL_MONEYFLOW_HSGT),
    ("limit_list", settings.TBL_LIMIT_LIST),
    ("top_list", settings.TBL_TOP_LIST),
    ("top_inst", None),  # 随 top_list 采集
    ("block_trade", settings.TBL_BLOCK_TRADE),
    ("margin", settings.TBL_MARGIN_SUMMARY),
    ("fina_indicator", settings.TBL_FINA_INDICATOR),
    ("forecast", settings.TBL_FORECAST),
    ("express", settings.TBL_EXPRESS),
    ("dc_index", settings.TBL_DC_SECTOR_DAILY),
    ("dc_daily", settings.TBL_DC_SECTOR_KLINE),
    ("dc_member", settings.TBL_DC_SECTOR_MEMBER),
]
TARGETS = [(c, t) for c, t in TARGETS if t]

# 快照型 / 报告期型表：不做「逐交易日覆盖」判定
SNAPSHOT_TABLES = {settings.TBL_STOCK_BASIC, settings.TBL_TRADE_CALENDAR,
                   settings.TBL_DC_SECTOR_MEMBER}
PERIOD_TABLES = {settings.TBL_FINA_INDICATOR, settings.TBL_FORECAST,
                 settings.TBL_EXPRESS}


def _date_col(db, table):
    for cand in ("trade_date", "cal_date", "end_date", "ann_date",
                 "list_date", "delist_date", "snapshot_date"):
        if db.fetch_all("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t AND column_name=:c",
                        {"t": table, "c": cand}):
            return cand
    return None


def main():
    ap = argparse.ArgumentParser(description="采集覆盖度校验")
    ap.add_argument("--missing", action="store_true",
                    help="列出未覆盖的交易日（每表最多 20 个）")
    args = ap.parse_args()

    db = get_db_manager()
    start = settings.data.start_date
    end = settings.data.get_end_date()
    expected = [r["cal_date"] for r in db.fetch_all(
        "SELECT cal_date FROM trade_calendar WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date>=:s AND cal_date<=:e ORDER BY cal_date",
        {"s": start, "e": end})]
    exp_set = set(expected)
    print(f"范围 {start}~{end}，应有交易日 {len(expected)} 个")
    print("=" * 96)
    print(f"{'采集器':<16}{'表':<20}{'行数':>13}{'日期覆盖':>10}{'缺失':>8}  说明")
    print("-" * 96)

    incomplete = []
    for coll, table in TARGETS:
        cnt = db.fetch_one(f"SELECT count(*) AS c FROM {table}")["c"]
        col = _date_col(db, table)
        note = ""
        covered = missing = None
        if col and table not in SNAPSHOT_TABLES:
            rows = db.fetch_all(
                f"SELECT DISTINCT {col} AS d FROM {table} WHERE {col} IS NOT NULL")
            seen = {r["d"] for r in rows}
            if table in PERIOD_TABLES:
                note = f"报告期 {min(seen) if seen else '-'}~{max(seen) if seen else '-'}"
                covered = len(seen)
                missing = None
            else:
                missing_dates = sorted(exp_set - seen)
                covered = len(seen & exp_set)
                missing = len(missing_dates)
                note = (f"{min(seen)}~{max(seen)}" if seen else "无数据")
                if args.missing and missing_dates:
                    note += "  缺: " + ",".join(missing_dates[:20]) + \
                            (" …" if missing > 20 else "")
        else:
            note = "快照型（按行数判断）"

        flag = ""
        if table in SNAPSHOT_TABLES:
            if cnt == 0:
                flag = " ← 空表"
        elif table in PERIOD_TABLES:
            if cnt == 0:
                flag = " ← 空表"
        elif missing:
            flag = " ← 未采完"

        cov_s = "-" if covered is None else str(covered)
        mis_s = "-" if missing is None else str(missing)
        print(f"{coll:<16}{table:<20}{cnt:>13}{cov_s:>10}{mis_s:>8}  {note}{flag}")
        if flag:
            incomplete.append((coll, table, flag.strip(" ←")))

    print("-" * 96)
    print("断点状态（未成功的项）:")
    rows = db.fetch_all(
        "SELECT collector, status, count(*) AS c FROM collection_checkpoint "
        "WHERE status <> 'succeeded' GROUP BY collector, status "
        "ORDER BY collector, status")
    if not rows:
        print("  全部 succeeded")
    for r in rows:
        print(f"  {r['collector']:<16}{r['status']:<14}{r['c']}")

    print("失败日志（pending）:")
    rows = db.fetch_all(
        "SELECT collector, count(*) AS c FROM task_failure_log "
        "WHERE status='pending' GROUP BY collector ORDER BY 2 DESC")
    if not rows:
        print("  无")
    for r in rows:
        print(f"  {r['collector']:<16}{r['c']}")

    print("=" * 96)
    if incomplete:
        print(f"未达标 {len(incomplete)} 张："
              + ", ".join(f"{t}" for _, t, _ in incomplete))
    else:
        print("全部目标表采集完成 ✔")
    return 0 if not incomplete else 1


if __name__ == "__main__":
    sys.exit(main())
