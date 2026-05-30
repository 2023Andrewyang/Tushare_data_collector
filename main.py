# -*- coding: utf-8 -*-
"""stock-data-hub 统一 CLI 入口。

用法:
  python main.py init     [--start YYYYMMDD] [--end YYYYMMDD] [--schema-only] [--collector X]
  python main.py update   [--date YYYYMMDD]  [--start --end]  [--collector X]
  python main.py retry    [--collector X] [--date D] [--start --end]
  python main.py backfill --start --end [--collector X]
  python main.py status   [--failures] [--date D]
"""
import argparse

from core.logging_setup import setup_logging
from commands import cmd_init, cmd_update, cmd_retry, cmd_backfill, cmd_status


def build_parser():
    p = argparse.ArgumentParser(prog="stock-data-hub",
                                description="A 股行情数据中台 CLI")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="初始化全量采集")
    pi.add_argument("--start")
    pi.add_argument("--end")
    pi.add_argument("--schema-only", action="store_true", dest="schema_only")
    pi.add_argument("--collector")

    pu = sub.add_parser("update", help="增量更新")
    pu.add_argument("--date")
    pu.add_argument("--start")
    pu.add_argument("--end")
    pu.add_argument("--collector")

    pr = sub.add_parser("retry", help="重试失败任务")
    pr.add_argument("--collector")
    pr.add_argument("--date")
    pr.add_argument("--start")
    pr.add_argument("--end")

    pb = sub.add_parser("backfill", help="强制补录（覆盖写）")
    pb.add_argument("--start", required=True)
    pb.add_argument("--end", required=True)
    pb.add_argument("--collector")

    ps = sub.add_parser("status", help="查看状态")
    ps.add_argument("--failures", action="store_true")
    ps.add_argument("--date")
    return p


def main():
    setup_logging()
    args = build_parser().parse_args()
    handler = {
        "init": cmd_init,
        "update": cmd_update,
        "retry": cmd_retry,
        "backfill": cmd_backfill,
        "status": cmd_status,
    }[args.command]
    handler.run(args)


if __name__ == "__main__":
    main()
