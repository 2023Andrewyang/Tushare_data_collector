# -*- coding: utf-8 -*-
"""上线前体检：用真实接口数据核对 schema 列宽，并验证 dc_member 快照行为。

不写库（top_list 的 top_inst 落库副作用已绕开），只做一次性抽样。
用法: python scripts/check_widths.py
"""
import os
import sys

sys.path.insert(0, ".")
os.environ.setdefault("USERPROFILE", os.path.join(os.getcwd(), ".tushare_home"))

import pandas as pd  # noqa: E402
from sqlalchemy import String  # noqa: E402

from config.settings import settings  # noqa: E402
from collectors import COLLECTOR_REGISTRY  # noqa: E402
from collectors.top_list import _LIST_FIELDS, _INST_FIELDS  # noqa: E402
from core.tushare_client import get_tushare_client  # noqa: E402
from models.schema import TABLES  # noqa: E402

D = "20260910"
P = "20251231"

# (采集器, 调用方式, 参数)
DATE_CASES = ["adj_factor", "stk_limit", "suspend", "stock_st", "moneyflow",
              "moneyflow_hsgt", "limit_list", "block_trade", "margin",
              "dc_index", "dc_daily"]
PERIOD_CASES = ["fina_indicator", "forecast", "express"]

client = get_tushare_client()


def check(coll_name, table_name, df):
    if df is None or df.empty:
        print(f"  [{coll_name}] 返回空，跳过列宽检查")
        return
    table = TABLES[table_name]
    problems = []
    for col in table.columns:
        if not isinstance(col.type, String) or not col.type.length:
            continue
        if col.name not in df.columns:
            continue
        series = df[col.name].dropna()
        if series.empty:
            continue
        maxlen = int(series.astype(str).str.len().max())
        if maxlen > col.type.length * 0.8:
            problems.append(f"{col.name}: 实测最大 {maxlen} / 列宽 {col.type.length}")
    flag = "  [WARN] " + "; ".join(problems) if problems else "  ok"
    print(f"  [{coll_name}] 行数={len(df)} 列宽检查{flag}")


print("=== 1) 列宽体检（真实数据抽样）===")
for name in DATE_CASES:
    Coll = COLLECTOR_REGISTRY[name]
    inst = Coll()
    df = inst.fetch_by_date(D)
    check(name, inst.TABLE_NAME, df)

for name in PERIOD_CASES:
    Coll = COLLECTOR_REGISTRY[name]
    inst = Coll()
    df = inst.fetch_by_period(P)
    check(name, inst.TABLE_NAME, df)

# top_list / top_inst：走接口但不落库
try:
    inst = COLLECTOR_REGISTRY["top_list"]()
    inst_l = client.query("top_list", trade_date=D, fields=_LIST_FIELDS)
    check("top_list", settings.TBL_TOP_LIST, inst_l)
    inst_i = client.query("top_inst", trade_date=D, fields=_INST_FIELDS)
    check("top_inst", settings.TBL_TOP_INST, inst_i)
except Exception as e:  # noqa: BLE001
    print(f"  [top_list] 探测失败: {str(e)[:150]}")

# dc_member 快照
try:
    dm = COLLECTOR_REGISTRY["dc_member"]()
    df = dm.fetch_snapshot(start_date=None, end_date=D)
    check("dc_member", settings.TBL_DC_SECTOR_MEMBER, df)
except Exception as e:  # noqa: BLE001
    print(f"  [dc_member] 探测失败: {str(e)[:150]}")

print()
print("=== 2) dc_member 快照行为核对 ===")
try:
    a = client.query("dc_member", trade_date=D, fields="ts_code,con_code,name,trade_date")
    print(f"  仅 trade_date={D}: 行数={len(a)}，板块数={a['ts_code'].nunique() if not a.empty else 0}")
    idx = client.query("dc_index", trade_date=D, fields="ts_code,name")
    print(f"  dc_index {D}: 板块数={len(idx)}")
    if not idx.empty:
        code = idx.iloc[0]["ts_code"]
        b = client.query("dc_member", ts_code=code, fields="ts_code,con_code,name")
        print(f"  指定 ts_code={code}: 行数={len(b)}")
    # 日期间隔抽样，看是否每天都在变
    for d in ("20260803", "20260810", "20260910"):
        c = client.query("dc_member", trade_date=d, fields="ts_code,con_code")
        print(f"  trade_date={d}: 行数={len(c)}")
except Exception as e:  # noqa: BLE001
    print(f"  探测失败: {str(e)[:200]}")
