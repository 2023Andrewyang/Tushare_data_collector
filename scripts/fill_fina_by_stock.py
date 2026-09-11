# -*- coding: utf-8 -*-
"""按个股补齐 fina_indicator 的报告期。

代理对个别报告期（20230331、20260630）的"整期全市场"查询稳定返回 HTTP 400
（结果集过大导致其上游失败），但按单只股票查询完全正常（0.5s/次）。本脚本
用多线程逐股补齐这些报告期，写入走采集器自身的 save()（schema 对齐 + 幂等）。

用法:
  python scripts/fill_fina_by_stock.py                     # 补默认的两个报告期
  python scripts/fill_fina_by_stock.py --periods 20230331 --workers 4
  python scripts/fill_fina_by_stock.py --periods 20260630 --missing-only
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from config.settings import settings  # noqa: E402
from core.logging_setup import setup_logging  # noqa: E402
from core.database import get_db_manager  # noqa: E402
from collectors import COLLECTOR_REGISTRY  # noqa: E402

DEFAULT_PERIODS = "20230331,20260630"


def main():
    ap = argparse.ArgumentParser(description="按个股补齐 fina_indicator 报告期")
    ap.add_argument("--periods", default=DEFAULT_PERIODS)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--missing-only", action="store_true",
                    help="只查询该报告期尚无记录的股票，用于中断后续跑或"
                         "收敛补齐，避免每次重复拉取全市场")
    args = ap.parse_args()

    setup_logging()
    db = get_db_manager()
    inst = COLLECTOR_REGISTRY["fina_indicator"]()
    codes = [r["ts_code"] for r in db.fetch_all(
        "SELECT ts_code FROM stock_basic ORDER BY ts_code")]
    periods = [p.strip() for p in args.periods.split(",") if p.strip()]

    tasks = []
    for p in periods:
        if args.missing_only:
            have = {r["ts_code"] for r in db.fetch_all(
                "SELECT DISTINCT ts_code FROM fina_indicator WHERE end_date=:p",
                {"p": p})}
            scope = [c for c in codes if c not in have]
            print(f"报告期 {p}: 已有 {len(have)} 只，待补 {len(scope)} 只", flush=True)
        else:
            scope = codes
        tasks.extend((p, c) for c in scope)

    print(f"股票 {len(codes)} 只 × 报告期 {len(periods)} 个，本次查询 {len(tasks)} 次，"
          f"并发 {args.workers}", flush=True)

    def fetch(task):
        p, c = task
        return p, c, inst.client.query("fina_indicator", ts_code=c, period=p)

    written = 0
    done = 0
    failed = 0
    buf = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(fetch, t) for t in tasks]
        for f in as_completed(futures):
            done += 1
            try:
                _, _, df = f.result()
            except Exception as e:  # noqa: BLE001
                failed += 1
                if failed <= 5:
                    print(f"  失败({failed}): {str(e)[:100]}", flush=True)
                continue
            if df is not None and not df.empty:
                buf.append(df)
            if len(buf) >= 200:
                written += inst.save(pd.concat(buf, ignore_index=True))["success"]
                buf = []
            if done % 1000 == 0:
                print(f"  {done}/{len(tasks)} 已写入≈{written}，失败={failed}",
                      flush=True)
    if buf:
        written += inst.save(pd.concat(buf, ignore_index=True))["success"]

    print(f"完成：查询 {done} 次，失败 {failed} 次，写入 {written} 行", flush=True)
    for p in periods:
        n = db.fetch_one(
            "SELECT count(1) AS c FROM fina_indicator WHERE end_date=:p",
            {"p": p})["c"]
        print(f"  end_date={p}: {n} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
