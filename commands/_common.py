# -*- coding: utf-8 -*-
"""命令层共用：结果汇总输出。"""


def print_summary(results: dict):
    """打印各采集器执行结果表格。

    results: {collector_name: {"success":int, "failed":int, "skipped":bool, ...}}
    """
    print("\n" + "=" * 64)
    print(f"{'采集器':<20}{'成功':>10}{'失败':>10}{'状态':>12}")
    print("-" * 64)
    total_s = total_f = 0
    for name, r in results.items():
        r = r or {}
        s = r.get("success", 0)
        f = r.get("failed", 0)
        total_s += s
        total_f += f
        if r.get("skipped"):
            state = "skipped"
        elif f > 0:
            state = "有失败"
        else:
            state = "ok"
        print(f"{name:<20}{s:>10}{f:>10}{state:>12}")
    print("-" * 64)
    print(f"{'合计':<20}{total_s:>10}{total_f:>10}")
    print("=" * 64)
