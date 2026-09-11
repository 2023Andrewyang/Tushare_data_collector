# -*- coding: utf-8 -*-
"""查看 PostgreSQL 活动连接，用于判断当前有几个采集进程在跑。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()
    print("活动连接（按 application_name / backend_start 分组）：")
    for r in db.fetch_all(
            "SELECT application_name, client_addr, state, count(*) AS c, "
            "min(backend_start) AS bstart, max(query_start) AS last_query "
            "FROM pg_stat_activity WHERE datname = current_database() "
            "GROUP BY application_name, client_addr, state "
            "ORDER BY bstart"):
        print(f"  app={str(r['application_name']):<20}state={str(r['state']):<22}"
              f"n={r['c']:<3} backend_start={r['bstart']} last_query={r['last_query']}")

    print("\n正在执行的 SQL：")
    rows = db.fetch_all(
        "SELECT pid, state, query_start, left(query, 90) AS q "
        "FROM pg_stat_activity WHERE datname = current_database() "
        "AND state <> 'idle' ORDER BY query_start")
    if not rows:
        print("  (无)")
    for r in rows:
        print(f"  pid={r['pid']} {r['state']} {r['query_start']} | {r['q']}")


if __name__ == "__main__":
    main()
