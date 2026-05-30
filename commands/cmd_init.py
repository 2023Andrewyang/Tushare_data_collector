# -*- coding: utf-8 -*-
"""init 命令：建表 + 全量采集。"""
import logging

from config.settings import settings
from core.database import get_db_manager
from core.failure_handler import get_failure_handler
from collectors import COLLECTOR_REGISTRY, BASIC_COLLECTORS
from commands._common import print_summary

logger = logging.getLogger(__name__)


def run(args):
    db = get_db_manager()
    db.create_all_tables()
    if getattr(args, "schema_only", False):
        print("建表完成（schema-only）")
        return

    start = args.start or settings.data.start_date
    end = args.end or settings.data.get_end_date()

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
        logger.info(f"=== init [{name}] {start} - {end} ===")
        try:
            results[name] = Coll().run_full(start, end)
        except KeyboardInterrupt:
            logger.warning("用户中断 init")
            break
        except Exception as e:
            logger.error(f"[{name}] init 异常: {e}")
            results[name] = {"success": 0, "failed": 1}

    print_summary(results)
    get_failure_handler().print_report()
