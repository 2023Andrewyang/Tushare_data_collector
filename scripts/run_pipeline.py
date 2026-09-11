# -*- coding: utf-8 -*-
"""并发采集全部采集器（可排除指定采集器）。

等价于 `main.py init`，但：
- 可排除若干采集器，默认排除已完成的 daily_quote。
- 统一使用 _update=True + _force=False：已有数据覆盖写，未完成项自动续传。
- 多线程并发（--workers，默认 4）：不同表之间互不依赖，各自维护断点。
- 单个采集器异常不影响其他采集器。
- 写 logs/pipeline_state.json，供 scripts/progress.py 读取。

用法:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --workers 6 --exclude daily_basic,daily_quote
  python scripts/run_pipeline.py --collector index_daily,adj_factor
"""
import argparse
import json
import logging
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.logging_setup import setup_logging  # noqa: E402
from core.failure_handler import get_failure_handler  # noqa: E402
from core.database import get_db_manager  # noqa: E402
from core.tushare_client import get_tushare_client  # noqa: E402
from core.checkpoint import get_checkpoint_manager  # noqa: E402
from collectors import COLLECTOR_REGISTRY, BASIC_COLLECTORS  # noqa: E402

logger = logging.getLogger("pipeline")

STATE_FILE = Path(settings.log.dir) / "pipeline_state.json"
DEFAULT_EXCLUDE = ["daily_quote"]

# 先派发「日频 × 1623 个交易日」的重活，最后派发廉价任务，最大化并发收益。
HEAVY_FIRST = [
    "moneyflow", "adj_factor", "index_daily", "stk_limit", "suspend",
    "stock_st", "moneyflow_hsgt", "limit_list", "top_list", "block_trade",
    "margin", "dc_index", "dc_daily",
    "dc_member", "fina_indicator", "forecast", "express",
]


def _order(exclude):
    """重活优先；基础采集器（stock_basic/trade_calendar）放最后。"""
    names = [n for n in HEAVY_FIRST if n in COLLECTOR_REGISTRY]
    names += BASIC_COLLECTORS
    names += [n for n in COLLECTOR_REGISTRY if n not in names]
    return [n for n in names if n not in exclude]


def _write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(STATE_FILE)


def _run_one(name, start, end):
    """在工作线程里跑单个采集器，返回 (name, result)。"""
    Coll = COLLECTOR_REGISTRY[name]
    t0 = time.time()
    logger.info(f"===== 开始 {name} | {start} ~ {end} =====")
    try:
        r = Coll().run_full(start, end, _update=True, _force=False)
        r = dict(r or {})
        r.setdefault("success", 0)
        r.setdefault("failed", 0)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{name}] 异常: {e}")
        logger.error(traceback.format_exc())
        r = {"success": 0, "failed": 1, "error": str(e)[:200]}
    r["elapsed_sec"] = round(time.time() - t0, 1)
    logger.info(f"===== 完成 {name} | {r} =====")
    return name, r


def main():
    parser = argparse.ArgumentParser(description="并发采集全部采集器")
    parser.add_argument("--exclude", default=",".join(DEFAULT_EXCLUDE),
                        help="逗号分隔的采集器名，默认排除 daily_quote")
    parser.add_argument("--start", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--workers", type=int, default=4, help="并发线程数")
    parser.add_argument("--collector", default=None,
                        help="只跑指定采集器（逗号分隔），便于调试")
    args = parser.parse_args()

    setup_logging()

    exclude = {x.strip() for x in (args.exclude or "").split(",") if x.strip()}
    if args.collector:
        names = [x.strip() for x in args.collector.split(",") if x.strip()]
    else:
        names = _order(exclude)
    names = [n for n in names if n not in exclude]

    start = args.start or settings.data.start_date
    end = args.end or settings.data.get_end_date()

    # 主线程预初始化单例 + 确保 checkpoint 表存在（避免多线程同时建表）
    get_db_manager()
    get_tushare_client()
    get_checkpoint_manager()

    state = {
        "current": None,
        "current_index": 0,
        "total": len(names),
        "running": [],
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "range": f"{start}~{end}",
        "exclude": sorted(exclude),
        "workers": args.workers,
        "results": {},
    }
    lock = threading.Lock()
    _write_state(state)

    logger.info("=" * 70)
    logger.info(f"流水线开始：{len(names)} 个采集器，范围 {start}~{end}，"
                f"并发 {args.workers}，排除 {sorted(exclude)}")
    logger.info("=" * 70)

    t_all = time.time()
    interrupted = False
    done = 0
    executor = ThreadPoolExecutor(max_workers=max(1, args.workers),
                                  thread_name_prefix="collector")
    futures = {executor.submit(_run_one, n, start, end): n for n in names}
    try:
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                name, r = fut.result()
            except Exception as e:  # noqa: BLE001
                r = {"success": 0, "failed": 1, "error": str(e)[:200]}
            with lock:
                done += 1
                state["results"][name] = r
                state["current"] = name
                state["current_index"] = done
                state["running"] = sorted(futures[f] for f in futures
                                          if not f.done())
                _write_state(state)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("用户中断，正在取消未开始的任务并保存状态…")
        for f in futures:
            f.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        state["interrupted"] = True
        state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["total_elapsed_sec"] = round(time.time() - t_all, 1)
        _write_state(state)
        get_failure_handler().print_report()
        # 立即退出：已提交的工作项状态由 checkpoint 保证可续传
        import os
        os._exit(130)

    executor.shutdown(wait=True)
    state["current"] = None
    state["running"] = []
    state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["total_elapsed_sec"] = round(time.time() - t_all, 1)
    _write_state(state)

    logger.info("=" * 70)
    logger.info(f"流水线结束，总耗时 {state['total_elapsed_sec']}s")
    for n in names:
        r = state["results"].get(n, {})
        logger.info(f"  {n:<18} success={r.get('success', 0):<9} "
                    f"failed={r.get('failed', 0):<4} "
                    f"skipped={r.get('skipped', False)} "
                    f"elapsed={r.get('elapsed_sec')}s")
    logger.info("=" * 70)
    try:
        get_failure_handler().print_report()
    except Exception as e:  # noqa: BLE001
        logger.error(f"失败报告输出异常: {e}")

    print(json.dumps(state["results"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
