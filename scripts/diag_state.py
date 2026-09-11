# -*- coding: utf-8 -*-
"""诊断脚本：查看断点(checkpoint)、各表行数与日期覆盖情况。

用法:
  python scripts/diag_state.py              # 概览
  python scripts/diag_state.py daily_basic  # 某个采集器的断点明细
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()
    print("=" * 78)
    print("1) collection_checkpoint 汇总（collector / status / 数量 / 范围）")
    print("=" * 78)
    rows = db.fetch_all(
        "SELECT collector, status, count(*) AS c, min(item_key) AS mn, max(item_key) AS mx "
        "FROM collection_checkpoint GROUP BY collector, status "
        "ORDER BY collector, status")
    if not rows:
        print("(空)")
    for r in rows:
        print(f"{r['collector']:<20}{r['status']:<14}{r['c']:>7}  "
              f"{r['mn']} ~ {r['mx']}")

    print()
    print("=" * 78)
    print("2) 各业务表行数与日期覆盖")
    print("=" * 78)
    tables = db.fetch_all(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name")
    for t in tables:
        name = t["table_name"]
        try:
            cnt = db.fetch_one(f"SELECT count(*) AS c FROM {name}")["c"]
        except Exception as e:  # noqa: BLE001
            print(f"{name:<22} 读取失败: {e}")
            continue
        date_col = None
        for cand in ("trade_date", "cal_date", "end_date", "ann_date", "snapshot_date"):
            cols = db.fetch_all(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name=:t AND column_name=:c", {"t": name, "c": cand})
            if cols:
                date_col = cand
                break
        if date_col:
            r = db.fetch_one(
                f"SELECT min({date_col}) AS mn, max({date_col}) AS mx FROM {name}")
            print(f"{name:<22}{cnt:>12}   {date_col}: {r['mn']} ~ {r['mx']}")
        else:
            print(f"{name:<22}{cnt:>12}   (无日期列)")

    print()
    print("=" * 78)
    print("3) task_failure_log 汇总")
    print("=" * 78)
    try:
        rows = db.fetch_all(
            "SELECT task_name, status, count(*) AS c FROM task_failure_log "
            "GROUP BY task_name, status ORDER BY task_name, status")
        if not rows:
            print("(无失败记录)")
        for r in rows:
            print(f"{r['task_name']:<20}{r['status']:<14}{r['c']:>7}")
    except Exception as e:  # noqa: BLE001
        print(f"读取失败: {e}")

    # 可选：某个采集器的断点明细（未成功的日期）
    if len(sys.argv) > 1:
        name = sys.argv[1]
        print()
        print("=" * 78)
        print(f"4) [{name}] 未成功的断点项")
        print("=" * 78)
        rows = db.fetch_all(
            "SELECT item_type, item_key, status, attempt_count, last_error "
            "FROM collection_checkpoint WHERE collector=:n AND status <> 'succeeded' "
            "ORDER BY item_key LIMIT 50", {"n": name})
        if not rows:
            print("(全部成功)")
        for r in rows:
            print(f"{r['item_type']:<10}{r['item_key']:<24}{r['status']:<14}"
                  f"attempts={r['attempt_count']}  {str(r['last_error'])[:60]}")
        agg = db.fetch_one(
            "SELECT count(*) FILTER (WHERE status='succeeded') AS ok, "
            "count(*) FILTER (WHERE status='failed') AS bad, "
            "count(*) FILTER (WHERE status='interrupted') AS intr, "
            "count(*) FILTER (WHERE status='running') AS run, "
            "count(*) AS total FROM collection_checkpoint WHERE collector=:n",
            {"n": name})
        print()
        print(f"[{name}] succeeded={agg['ok']} failed={agg['bad']} "
              f"interrupted={agg['intr']} running={agg['run']} total={agg['total']}")


if __name__ == "__main__":
    main()
