# -*- coding: utf-8 -*-
"""计算候选区间的交易日数量，用于判定当前运行的范围。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import get_db_manager  # noqa: E402


def main():
    db = get_db_manager()

    def cnt(s, e):
        r = db.fetch_one(
            "SELECT count(*) AS c FROM trade_calendar WHERE exchange='SSE' "
            "AND is_open=1 AND cal_date>=:s AND cal_date<=:e", {"s": s, "e": e})
        return r["c"]

    for s in ("20200102", "20230505", "20230508", "20230313", "20230605",
              "20230612", "20230613", "20220101", "20230101"):
        print(f"  {s} ~ 20260910 : {cnt(s, '20260910')} 个交易日")
    print()
    print(f"  20200102 ~ 20230504 : {cnt('20200102', '20230504')}")
    print(f"  20200102 ~ 20230602 : {cnt('20200102', '20230602')}")
    print(f"  20200102 ~ 20230609 : {cnt('20200102', '20230609')}")

    # daily_basic 当前实际覆盖
    r = db.fetch_one("SELECT count(DISTINCT trade_date) AS c, count(*) AS n FROM daily_basic")
    print(f"\n  daily_basic: 覆盖交易日={r['c']} 行数={r['n']}")
    rows = db.fetch_all("""
        WITH d AS (SELECT DISTINCT trade_date FROM daily_basic)
        SELECT min(trade_date) AS mn, max(trade_date) AS mx FROM d""")
    print(f"  日期范围: {rows[0]['mn']} ~ {rows[0]['mx']}")


if __name__ == "__main__":
    main()
