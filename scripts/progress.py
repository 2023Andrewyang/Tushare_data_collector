# -*- coding: utf-8 -*-
"""采集进度看板：当前正在跑的采集器、每个采集器的完成日期、剩余时间。

用法:
  python scripts/progress.py            # 打印一次
  python scripts/progress.py --watch 30 # 每 30 秒刷新，Ctrl+C 退出
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.database import get_db_manager  # noqa: E402

TABLE_OF = {
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
    "block_trade": settings.TBL_BLOCK_TRADE,
    "margin": settings.TBL_MARGIN_SUMMARY,
    "fina_indicator": settings.TBL_FINA_INDICATOR,
    "forecast": settings.TBL_FORECAST,
    "express": settings.TBL_EXPRESS,
    "dc_index": settings.TBL_DC_SECTOR_DAILY,
    "dc_daily": settings.TBL_DC_SECTOR_KLINE,
    "dc_member": settings.TBL_DC_SECTOR_MEMBER,
}

# [进度] 模块=xxx | 当前日期=yyy | 进度=12.34% (5/40) | 预计剩余=00:02:18
PROG_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,\d]* - [^-]* - INFO - "
    r"\[进度\] 模块=(?P<module>\S+) \| (?P<item_label>[^=|]+)=(?P<item>\S+) \| "
    r"进度=(?P<percent>[\d.]+)% \((?P<done>\d+)/(?P<total>\d+)\) \| "
    r"预计剩余=(?P<eta>\S+)")


def latest_progress():
    """从日志尾部取每个模块最后一次进度。"""
    fp = Path(settings.log.dir) / "data_hub.log"
    if not fp.exists():
        return {}
    text = fp.read_text(encoding="utf-8", errors="replace")[-200000:]
    out = {}
    for line in text.splitlines():
        m = PROG_RE.search(line)
        if m:
            out[m.group("module")] = m.groupdict()
    return out


def _date_col(db, table):
    for cand in ("trade_date", "cal_date", "end_date", "ann_date",
                 "list_date", "delist_date", "snapshot_date"):
        if db.fetch_all("SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t AND column_name=:c",
                        {"t": table, "c": cand}):
            return cand
    return None


def render():
    db = get_db_manager()
    start = settings.data.start_date
    end = settings.data.get_end_date()
    cal = db.fetch_one(
        "SELECT COUNT(*) AS c FROM " + settings.TBL_TRADE_CALENDAR +
        " WHERE exchange='SSE' AND is_open=1 AND cal_date>=:s AND cal_date<=:e",
        {"s": start, "e": end})
    total_days = cal["c"] if cal else 0

    print("=" * 100)
    print(f"采集进度看板   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
          f"   范围 {start}~{end}   交易日 {total_days} 天")

    state_fp = Path(settings.log.dir) / "pipeline_state.json"
    state = None
    if state_fp.exists():
        try:
            state = json.loads(state_fp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            state = None
    if state:
        cur = state.get("current")
        if cur or not state.get("finished_at"):
            print(f"当前采集器: {cur}  ({state.get('current_index')}/"
                  f"{state.get('total')})   该阶段开始: {state.get('started_at')}")
            running = state.get("running") or []
            if running:
                print(f"并发进行中: {', '.join(running)}")
        else:
            print(f"流水线已结束: {state.get('finished_at')}   "
                  f"总耗时 {state.get('total_elapsed_sec')}s")
            if state.get("interrupted"):
                print("（上次被中断，重跑相同命令即可续传）")
    else:
        print("（未发现 logs/pipeline_state.json，非流水线方式运行）")

    checkpoints = {}
    for r in db.fetch_all(
            "SELECT collector, status, COUNT(*) AS c FROM collection_checkpoint "
            "GROUP BY collector, status"):
        checkpoints.setdefault(r["collector"], {})[r["status"]] = r["c"]

    progress = latest_progress()

    print("-" * 100)
    print(f"{'采集器':<16}{'表名':<20}{'行数':>12}  {'当前进度':<34}{'成功':>7}"
          f"{'空':>6}{'失败':>6}{'中断':>6}")
    print("-" * 100)
    for name, table in TABLE_OF.items():
        try:
            cnt = db.fetch_one(f"SELECT COUNT(*) AS c FROM {table}")["c"]
        except Exception as e:  # noqa: BLE001
            cnt = f"ERR({str(e)[:20]})"
        cp = checkpoints.get(name, {})
        ok = cp.get("succeeded", 0)
        emp = cp.get("empty", 0)
        bad = cp.get("failed", 0)
        intr = cp.get("interrupted", 0) + cp.get("running", 0)
        p = progress.get(name)
        cell = (f"{p['item']} {p['percent']}% ({p['done']}/{p['total']}) "
                f"剩{p['eta']}") if p else "-"
        if len(cell) > 42:
            cell = cell[:42]
        print(f"{name:<16}{table:<20}{cnt:>12}  {cell:<44}{ok:>7}{emp:>6}"
              f"{bad:>6}{intr:>6}")

    pending = db.fetch_one(
        "SELECT COUNT(*) AS c FROM " + settings.TBL_TASK_FAILURE_LOG +
        " WHERE status='pending'")
    print("-" * 100)
    print(f"失败日志待处理: {pending['c'] if pending else 0}"
          f"    （空=接口返回 0 行，下次 --resume 会自动重试；失败=真异常）")
    print("=" * 100)


def main():
    ap = argparse.ArgumentParser(description="采集进度看板")
    ap.add_argument("--watch", type=int, default=0, metavar="SEC",
                    help="每 SEC 秒刷新一次")
    args = ap.parse_args()
    while True:
        try:
            render()
            if not args.watch:
                return
            time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n已退出。")
            return


if __name__ == "__main__":
    main()
