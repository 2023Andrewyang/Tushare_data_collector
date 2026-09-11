# -*- coding: utf-8 -*-
"""排查 daily_basic 是否采集完整。

判断口径（四条互相独立、可交叉验证）：
  1) 日期覆盖：表内 trade_date 去重后与 trade_calendar(SSE 开市日) 对比，
     差集即"整日缺失"。
  2) 每日行数分布：用中位数做基准，行数显著低于中位数的日期是"半截日"
     （代理分段返回或中途失败会造成这种形态）。
  3) 与 daily_quote 逐日对齐：两张表都是"每股每交易日一行"，同一交易日的
     行数应当接近；daily_basic 明显少于 daily_quote 的日期即可疑。
  4) 断点与失败日志：collection_checkpoint 里 daily_basic 的非 succeeded 项，
     以及 task_failure_log 中 pending 的日期。

用法:
  python scripts/check_daily_basic.py
  python scripts/check_daily_basic.py --list 40   # 缺失/异常日期最多列 40 个
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from core.database import get_db_manager  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="daily_basic 完整性排查")
    ap.add_argument("--list", type=int, default=30, help="每类最多列出多少个日期")
    ap.add_argument("--ratio", type=float, default=0.9,
                    help="与 daily_quote 对比的容忍比例，默认 0.9")
    args = ap.parse_args()

    db = get_db_manager()
    start = settings.data.start_date
    end = settings.data.get_end_date()
    expected = [r["cal_date"] for r in db.fetch_all(
        "SELECT cal_date FROM trade_calendar WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date>=:s AND cal_date<=:e ORDER BY cal_date",
        {"s": start, "e": end})]
    exp_set = set(expected)
    print(f"范围 {start}~{end}：应有交易日 {len(expected)} 个")

    # ---------- 0) 是否仍在采集 ----------
    n1 = db.fetch_one("SELECT count(1) AS c FROM daily_basic")["c"]
    time.sleep(10)
    n2 = db.fetch_one("SELECT count(1) AS c FROM daily_basic")["c"]
    print(f"行数：{n1} → {n2}"
          + ("（10 秒内在增长，说明仍有进程在写入）" if n2 != n1 else "（10 秒内无变化）"))

    # ---------- 1) 日期覆盖 ----------
    rows = db.fetch_all(
        "SELECT trade_date, count(1) AS c FROM daily_basic "
        "WHERE trade_date IS NOT NULL GROUP BY trade_date ORDER BY trade_date")
    per_date = {r["trade_date"]: r["c"] for r in rows}
    seen = set(per_date)
    missing = [d for d in expected if d not in seen]
    outside = sorted(seen - exp_set)
    print(f"\n[1] 日期覆盖：覆盖 {len(seen & exp_set)}/{len(expected)} 个交易日，"
          f"缺 {len(missing)} 个，范围 "
          f"{min(seen) if seen else '-'}~{max(seen) if seen else '-'}")
    if outside:
        print(f"    另有 {len(outside)} 个非交易日/范围外日期（前几个：{outside[:5]}）")
    if missing:
        print(f"    缺失日期（前 {args.list} 个）：{missing[:args.list]}")

    # ---------- 2) 每日行数分布 ----------
    if per_date:
        counts = list(per_date.values())
        med = int(statistics.median(counts))
        low = sorted([(d, c) for d, c in per_date.items() if c < med * 0.8])
        print(f"\n[2] 每日行数：中位数 {med}，最小 {min(counts)}"
              f"（{min(per_date, key=per_date.get)}），最大 {max(counts)}")
        print(f"    低于中位数 80% 的日期：{len(low)} 个")
        for d, c in low[:args.list]:
            print(f"      {d}: {c} 行（中位数 {med}）")

    # ---------- 3) 与 daily_quote 逐日对齐 ----------
    q = {r["trade_date"]: r["c"] for r in db.fetch_all(
        "SELECT trade_date, count(1) AS c FROM daily_quote "
        "WHERE trade_date IS NOT NULL GROUP BY trade_date")}
    gaps = []
    for d in sorted(exp_set & set(q)):
        b = per_date.get(d, 0)
        if b < q[d] * args.ratio:
            gaps.append((d, b, q[d]))
    print(f"\n[3] 与 daily_quote 逐日对齐：共同交易日 "
          f"{len(exp_set & set(q))} 个，其中 daily_basic 行数 < quote×{args.ratio} "
          f"的日期 {len(gaps)} 个")
    for d, b, qq in gaps[:args.list]:
        print(f"      {d}: daily_basic={b} vs daily_quote={qq}"
              f"（少 {qq - b}，{(1 - b / qq) * 100:.1f}%）")

    # ---------- 3b) 逐日缺口分布 ----------
    common = sorted(exp_set & set(q))
    deltas = sorted(((q[d] - per_date.get(d, 0), d) for d in common), reverse=True)
    short = [x for x in deltas if x[0] > 0]
    print(f"    [3b] 缺口分布：daily_basic 行数少于 daily_quote 的日期 {len(short)} 个"
          f"（占 {len(short) / max(1, len(common)) * 100:.1f}%），"
          f"最大缺口 {deltas[0][0] if deltas else 0} 行")
    if short:
        for gap, d in short[:10]:
            print(f"      {d}: quote={q[d]} basic={per_date.get(d, 0)}"
                  f" 少 {gap} 行（{gap / q[d] * 100:.1f}%）")

    # ---------- 4) 断点与失败日志 ----------
    print("\n[4] collection_checkpoint（collector='daily_basic'）:")
    for r in db.fetch_all(
            "SELECT status, count(1) AS c, min(item_key) AS mn, max(item_key) AS mx "
            "FROM collection_checkpoint WHERE collector='daily_basic' "
            "GROUP BY status ORDER BY status"):
        print(f"      {r['status']:<12}{r['c']:>6}   {r['mn']} ~ {r['mx']}")
    bad = db.fetch_all(
        "SELECT item_key, status FROM collection_checkpoint "
        "WHERE collector='daily_basic' AND status NOT IN ('succeeded','empty') "
        "ORDER BY item_key")
    if bad:
        print(f"    未成功项 {len(bad)} 个（前 {args.list} 个）：")
        for r in bad[:args.list]:
            print(f"      {r['item_key']}  {r['status']}")

    print("\n[5] task_failure_log（collector='daily_basic'）:")
    for r in db.fetch_all(
            "SELECT status, count(1) AS c, min(trade_date) AS mn, max(trade_date) AS mx "
            "FROM task_failure_log WHERE collector='daily_basic' "
            "GROUP BY status ORDER BY status"):
        print(f"      {r['status']:<10}{r['c']:>5}   {r['mn']} ~ {r['mx']}")
    fl = db.fetch_all(
        "SELECT trade_date, error_type FROM task_failure_log "
        "WHERE collector='daily_basic' ORDER BY trade_date")
    if fl:
        print(f"    失败日期 {len(fl)} 个：" +
              ", ".join(r["trade_date"] for r in fl[:args.list]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
