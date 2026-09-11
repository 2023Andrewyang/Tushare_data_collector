# -*- coding: utf-8 -*-
"""补洞：把"表里没有数据的交易日"对应的工作项重置为待处理，然后重跑该采集器。

背景：代理在并发压力下会偶发地对整个交易日返回 0 行。修复前的代码把这种
0 行响应记为 succeeded，导致这些日期被永久跳过。本脚本据此反查空洞、重置
断点（'empty'，可被 claim）并重跑，直到没有新的空洞被填上。

用法:
  python scripts/fill_holes.py                        # 默认处理本轮已完成的采集器
  python scripts/fill_holes.py --collectors suspend,limit_list --passes 2
  python scripts/fill_holes.py --all --passes 1       # 处理所有日频采集器
  python scripts/fill_holes.py --dry-run              # 只报告空洞，不改库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.database import get_db_manager  # noqa: E402
from core.logging_setup import setup_logging  # noqa: E402
from collectors import COLLECTOR_REGISTRY  # noqa: E402

# 采集器 -> (表名, 日期列)
TARGETS = {
    "suspend": (settings.TBL_SUSPEND, "trade_date"),
    "stock_st": (settings.TBL_STOCK_ST, "trade_date"),
    "moneyflow_hsgt": (settings.TBL_MONEYFLOW_HSGT, "trade_date"),
    "limit_list": (settings.TBL_LIMIT_LIST, "trade_date"),
    "adj_factor": (settings.TBL_ADJ_FACTOR, "trade_date"),
    "stk_limit": (settings.TBL_STK_LIMIT, "trade_date"),
    "index_daily": (settings.TBL_INDEX_DAILY, "trade_date"),
    "moneyflow": (settings.TBL_MONEYFLOW, "trade_date"),
    "top_list": (settings.TBL_TOP_LIST, "trade_date"),
    "top_inst": (settings.TBL_TOP_INST, "trade_date"),
    "block_trade": (settings.TBL_BLOCK_TRADE, "trade_date"),
    "margin": (settings.TBL_MARGIN_SUMMARY, "trade_date"),
    "dc_index": (settings.TBL_DC_SECTOR_DAILY, "trade_date"),
    "dc_daily": (settings.TBL_DC_SECTOR_KLINE, "trade_date"),
}
DEFAULT = ["suspend", "stock_st", "moneyflow_hsgt", "limit_list"]

# 有些表由别的采集器顺带写入（top_inst 由 top_list 一次抓两表）：
# 补洞时要用对应采集器重跑，并重置它名下的断点。
COLLECTOR_FOR = {"top_inst": "top_list"}

# 代理侧已知的起始覆盖日期：早于该日期的空洞是接口本身没有数据，
# 反复重试只会白耗配额。实测 dc_index 仅提供 20241225 起的东财板块数据。
MIN_DATE = {"dc_index": "20241225"}

# 报告期型采集器 -> 表名（按报告期而非交易日核对）
PERIOD_TARGETS = {
    "fina_indicator": settings.TBL_FINA_INDICATOR,
    "forecast": settings.TBL_FORECAST,
    "express": settings.TBL_EXPRESS,
}


def gen_periods(start, end):
    sy, ey = int(start[:4]), int(end[:4])
    out = []
    for y in range(sy, ey + 1):
        for q in ("0331", "0630", "0930", "1231"):
            p = f"{y}{q}"
            if start <= p <= end:
                out.append(p)
    return sorted(out)


def fill_periods(db, name, table, start, end, dry_run=False):
    expected = gen_periods(start, end)
    seen = {r["end_date"] for r in db.fetch_all(
        f"SELECT DISTINCT end_date FROM {table} WHERE end_date IS NOT NULL")}
    miss = [p for p in expected if p not in seen]
    print(f"[{name}] 应有报告期 {len(expected)}，缺 {len(miss)}"
          + (f" {miss}" if miss else ""))
    if not miss or dry_run:
        return
    for p in miss:
        db.execute(
            "UPDATE collection_checkpoint SET status='empty', updated_at=now() "
            "WHERE collector=:c AND item_type='period' AND item_key=:k", {"c": name, "k": p})
    r = COLLECTOR_REGISTRY[name]().run_full(start, end)
    seen2 = {x["end_date"] for x in db.fetch_all(
        f"SELECT DISTINCT end_date FROM {table} WHERE end_date IS NOT NULL")}
    left = [p for p in expected if p not in seen2]
    print(f"    重跑结果 {r}；剩余缺失报告期 {len(left)} {left}")


def expected_dates(db, start, end):
    rows = db.fetch_all(
        "SELECT cal_date FROM trade_calendar WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date>=:s AND cal_date<=:e ORDER BY cal_date", {"s": start, "e": end})
    return [r["cal_date"] for r in rows]


def missing_dates(db, table, col, expected):
    seen = {r[col] for r in db.fetch_all(
        f"SELECT DISTINCT {col} AS {col} FROM {table} WHERE {col} IS NOT NULL")}
    return [d for d in expected if d not in seen]


def reset_checkpoints(db, collector, dates):
    if not dates:
        return 0
    n = 0
    for d in dates:
        n += db.execute(
            "UPDATE collection_checkpoint SET status='empty', updated_at=now() "
            "WHERE collector=:c AND item_type='date' AND item_key=:k "
            "AND status='succeeded'", {"c": collector, "k": d}) or 0
    return n


def main():
    ap = argparse.ArgumentParser(description="补洞：重置空洞工作项并重跑")
    ap.add_argument("--collectors", default=None, help="逗号分隔；默认本轮已完成的 4 个")
    ap.add_argument("--all", action="store_true", help="处理所有日频采集器")
    ap.add_argument("--periods", action="store_true", help="只处理报告期型（财务）采集器")
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    setup_logging()
    db = get_db_manager()
    start = settings.data.start_date
    end = settings.data.get_end_date()
    expected = expected_dates(db, start, end)

    if args.periods:
        for p in range(1, args.passes + 1):
            print(f"===== 报告期第 {p}/{args.passes} 轮 =====")
            for name, table in PERIOD_TARGETS.items():
                fill_periods(db, name, table, start, end, args.dry_run)
        print("完成")
        return 0

    if args.all:
        names = list(TARGETS)
    elif args.collectors:
        names = [x.strip() for x in args.collectors.split(",") if x.strip()]
    else:
        names = DEFAULT

    print(f"范围 {start}~{end}，应有交易日 {len(expected)} 个")
    for p in range(1, args.passes + 1):
        print(f"===== 第 {p}/{args.passes} 轮 =====")
        for name in names:
            table, col = TARGETS[name]
            exp = [d for d in expected if d >= MIN_DATE.get(name, "00000000")]
            miss = missing_dates(db, table, col, exp)
            print(f"[{name}] 空洞 {len(miss)} 个", end="")
            if not miss or args.dry_run:
                print(" -> 跳过")
                continue
            print(f" -> 重置断点并重跑（{miss[:3]}...）")
            ck = COLLECTOR_FOR.get(name, name)
            reset_checkpoints(db, ck, miss)
            r = COLLECTOR_REGISTRY[ck]().run_full(start, end)
            after = missing_dates(db, table, col, exp)
            print(f"    重跑结果 {r}；剩余空洞 {len(after)} 个"
                  f"（填上 {len(miss) - len(after)}）")
    print("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
