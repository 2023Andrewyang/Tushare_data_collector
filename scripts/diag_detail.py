# -*- coding: utf-8 -*-
"""查看 daily_basic 断点细节、失败日志明细。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()
    print("=" * 80)
    print("daily_basic checkpoint：未成功项")
    rows = db.fetch_all(
        "SELECT item_key, status, attempt_count, last_error FROM collection_checkpoint "
        "WHERE collector='daily_basic' AND status <> 'succeeded' ORDER BY item_key")
    for r in rows:
        print(f"  {r['item_key']}  {r['status']}  attempts={r['attempt_count']}  "
              f"err={str(r['last_error'])[:80]}")

    print()
    print("已成功的 daily_basic 日期 > 20230601 的：")
    rows = db.fetch_all(
        "SELECT item_key FROM collection_checkpoint WHERE collector='daily_basic' "
        "AND status='succeeded' AND item_key > '20230601' ORDER BY item_key")
    print("  " + (", ".join(r["item_key"] for r in rows) or "(无)"))

    print()
    print("daily_basic 表最后有数据的 10 个交易日：")
    rows = db.fetch_all("SELECT DISTINCT trade_date FROM daily_basic "
                        "ORDER BY trade_date DESC LIMIT 10")
    print("  " + ", ".join(r["trade_date"] for r in rows))

    print()
    print("=" * 80)
    print("task_failure_log 明细")
    rows = db.fetch_all("SELECT * FROM task_failure_log ORDER BY id")
    for r in rows:
        print("  " + str(dict(r)))

    print()
    print("collection_checkpoint 表结构：")
    for r in db.fetch_all(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='collection_checkpoint' ORDER BY ordinal_position"):
        print(f"  {r['column_name']:<16}{r['data_type']}")


if __name__ == "__main__":
    main()
