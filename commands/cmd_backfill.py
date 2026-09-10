# -*- coding: utf-8 -*-
"""backfill 命令：强制补录（覆盖写）。"""
import logging

from core.failure_handler import get_failure_handler
from collectors import COLLECTOR_REGISTRY, BASIC_COLLECTORS
from commands._common import print_summary

logger = logging.getLogger(__name__)


def run(args):
    start, end = args.start, args.end

    if args.collector:
        names = [args.collector]
    else:
        names = BASIC_COLLECTORS + [n for n in COLLECTOR_REGISTRY
                                    if n not in BASIC_COLLECTORS]

    results = {}
    for name in names:
        Coll = COLLECTOR_REGISTRY.get(name)
        if Coll is None:
            logger.error(f"未知采集器: {name}")
            continue
        logger.info(f"=== backfill [{name}] {start} - {end} (覆盖写) ===")
        try:
            results[name] = Coll().run_backfill(
                start, end, resume=getattr(args, "resume", False))
        except KeyboardInterrupt:
            logger.warning("用户中断 backfill")
            break
        except Exception as e:
            logger.error(f"[{name}] backfill 异常: {e}")
            results[name] = {"success": 0, "failed": 1}

    print_summary(results)
    get_failure_handler().print_report()
