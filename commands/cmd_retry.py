# -*- coding: utf-8 -*-
"""retry 命令：重试失败任务。"""
import logging

from core.failure_handler import get_failure_handler
from collectors import COLLECTOR_REGISTRY, PeriodBasedCollector

logger = logging.getLogger(__name__)


def run(args):
    fh = get_failure_handler()
    pending = fh.get_pending(collector=args.collector, trade_date=args.date,
                             start_date=args.start, end_date=args.end)
    if not pending:
        print("没有待重试的失败任务。")
        return

    print(f"共 {len(pending)} 条待重试任务")
    success = failed = 0
    # 采集器实例缓存
    cache = {}
    for rec in pending:
        name = rec["collector"]
        Coll = COLLECTOR_REGISTRY.get(name)
        if Coll is None:
            logger.warning(f"未知采集器 {name}，跳过失败记录 id={rec['id']}")
            continue
        collector = cache.get(name) or cache.setdefault(name, Coll())
        trade_date = rec.get("trade_date")
        try:
            r = collector.run_incremental(trade_date)
            if r.get("failed", 0) == 0 and not r.get("skipped"):
                fh.mark_resolved(rec["id"])
                success += 1
                logger.info(f"重试成功: {name} @ {trade_date} (id={rec['id']})")
            else:
                failed += 1
        except Exception as e:
            logger.error(f"重试失败: {name} @ {trade_date}: {e}")
            failed += 1

    print(f"\n重试完成：成功 {success}，仍失败 {failed}")
    fh.print_report()
