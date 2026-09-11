# -*- coding: utf-8 -*-
"""精简查看 daily_basic 断点与失败日志（错误信息截断）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()
    print("=" * 80)
    print("[daily_basic] 未成功的断点项")
    for r in db.fetch_all(
            "SELECT item_key, status, attempt_count, last_error FROM collection_checkpoint "
            "WHERE collector='daily_basic' AND status <> 'succeeded' ORDER BY item_key"):
        print(f"  {r['item_key']}  {r['status']}  attempts={r['attempt_count']}  "
              f"err={str(r['last_error'])[:60]}")

    print()
    print("[daily_basic] 已成功且日期 > 20230601 的断点：")
    rows = db.fetch_all(
        "SELECT item_key FROM collection_checkpoint WHERE collector='daily_basic' "
        "AND status='succeeded' AND item_key > '20230601' ORDER BY item_key")
    print("  " + (", ".join(r["item_key"] for r in rows) or "(无)"))

    print()
    print("[daily_basic] 表内有数据的最后 8 个交易日：")
    rows = db.fetch_all("SELECT DISTINCT trade_date FROM daily_basic "
                        "ORDER BY trade_date DESC LIMIT 8")
    print("  " + ", ".join(r["trade_date"] for r in rows))

    print()
    print("[daily_basic] 表内 2023-05-25 ~ 2023-06-10 段有数据的日期：")
    rows = db.fetch_all("SELECT DISTINCT trade_date FROM daily_basic "
                        "WHERE trade_date BETWEEN '20230525' AND '20230610' "
                        "ORDER BY trade_date")
    print("  " + ", ".join(r["trade_date"] for r in rows))

    print()
    print("=" * 80)
    print("task_failure_log（截断错误信息）")
    for r in db.fetch_all(
            "SELECT id, collector, trade_date, error_type, status, retry_count, "
            "left(error_message, 70) AS msg FROM task_failure_log ORDER BY id"):
        print(f"  id={r['id']:<3}{r['collector']:<14}{str(r['trade_date']):<12}"
              f"{r['error_type']:<18}{r['status']:<10}retry={r['retry_count']}  "
              f"{r['msg']}")


if __name__ == "__main__":
    main()
