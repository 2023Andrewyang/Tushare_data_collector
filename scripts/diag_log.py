# -*- coding: utf-8 -*-
"""解析 data_hub.log：列出最近的 init 区间、并发的进度流。"""
import re
import sys
from collections import OrderedDict
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "logs" / "data_hub.log"

INIT_RE = re.compile(r"^(\S+ \S+) - commands\.\w+ - INFO - === \w+ \[(\w+)\] (\S+) - (\S+) ===")
PROG_RE = re.compile(r"^(\S+ \S+) - collectors\.base_collector - INFO - "
                     r"\[进度\] 模块=(\w+) \| 当前\S+=(\S+) \| 进度=([\d.]+)% \((\d+)/(\d+)\)")


def main():
    text = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"日志总行数: {len(text)}")

    print("\n--- 所有 === init/update [...] 区间（最后 20 条）---")
    inits = []
    for i, line in enumerate(text):
        m = INIT_RE.match(line)
        if m:
            inits.append((i, m.group(1), m.group(2), m.group(3), m.group(4)))
    for i, ts, cmd, name, rng in inits[-20:]:
        print(f"  line{i:<7}{ts}  {name:<16}{rng}")

    print("\n--- 日志最后一个 === init 标记之后的进度流（按 total 分组）---")
    last_init = inits[-1][0] if inits else 0
    print(f"  最后一个 init 在 line {last_init}: "
          f"{inits[-1][1]} {inits[-1][2]} {inits[-1][3]}-{inits[-1][4]}" if inits else "  无")
    groups = OrderedDict()
    for i in range(last_init, len(text)):
        m = PROG_RE.match(text[i])
        if not m:
            continue
        ts, mod, date, pct, done, total = m.groups()
        key = (mod, total)
        g = groups.setdefault(key, {"n": 0, "first": ts, "last": ts,
                                    "first_date": date, "last_date": date,
                                    "last_done": done})
        g["n"] += 1
        g["last"] = ts
        g["last_date"] = date
        g["last_done"] = done
    for (mod, total), g in groups.items():
        print(f"  模块={mod:<14} total={total:<6} 进度行数={g['n']:<6} "
              f"{g['first']} ({g['first_date']}) -> {g['last']} ({g['last_date']}) "
              f"done={g['last_done']}")

    print("\n--- 最近 60 行日志 ---")
    for line in text[-60:]:
        print("  " + line)


if __name__ == "__main__":
    main()
