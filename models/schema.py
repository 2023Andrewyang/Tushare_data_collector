# -*- coding: utf-8 -*-
"""全部数据表定义（SQLAlchemy Core）。列名 = Tushare 字段名。

这是「表有哪些列」的唯一真源。采集器据此对齐 DataFrame。
- 价格/量额用 Float（double precision）；金额/比率用 Numeric 避免精度丢失。
- 日期字段统一 String(8)，YYYYMMDD。
- 每张行情表都对 trade_date 建索引。
"""
from sqlalchemy import (MetaData, Table, Column, String, Float, Integer,
                        Numeric, Text, DateTime, Index, func)

metadata = MetaData()

# ============ 基础数据 ============
stock_basic = Table(
    "stock_basic", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("symbol", String(10)),
    Column("name", String(30)),
    Column("area", String(20)),
    Column("industry", String(30)),
    Column("fullname", String(100)),
    Column("market", String(10)),
    Column("exchange", String(10)),
    Column("curr_type", String(10)),
    Column("list_status", String(2)),
    Column("list_date", String(8)),
    Column("delist_date", String(8)),
    Column("is_hs", String(2)),
    Column("created_at", DateTime, server_default=func.now()),
)

trade_calendar = Table(
    "trade_calendar", metadata,
    Column("exchange", String(10), primary_key=True),
    Column("cal_date", String(8), primary_key=True),
    Column("is_open", Integer),
    Column("pretrade_date", String(8)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_trade_cal_date", trade_calendar.c.cal_date)

# ============ 行情数据 ============
daily_quote = Table(
    "daily_quote", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("open", Float), Column("high", Float),
    Column("low", Float), Column("close", Float),
    Column("pre_close", Float), Column("change", Float),
    Column("pct_chg", Numeric(15, 4)),
    Column("vol", Float), Column("amount", Float),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_daily_quote_date", daily_quote.c.trade_date)

daily_basic = Table(
    "daily_basic", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("close", Float),
    Column("turnover_rate", Numeric(15, 4)),
    Column("turnover_rate_f", Numeric(15, 4)),
    Column("volume_ratio", Numeric(15, 4)),
    Column("pe", Numeric(18, 4)), Column("pe_ttm", Numeric(18, 4)),
    Column("pb", Numeric(18, 4)),
    Column("ps", Numeric(18, 4)), Column("ps_ttm", Numeric(18, 4)),
    Column("dv_ratio", Numeric(15, 4)), Column("dv_ttm", Numeric(15, 4)),
    Column("total_share", Float), Column("float_share", Float),
    Column("free_share", Float),
    Column("total_mv", Numeric(20, 4)), Column("circ_mv", Numeric(20, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_daily_basic_date", daily_basic.c.trade_date)

index_daily = Table(
    "index_daily", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("open", Float), Column("high", Float),
    Column("low", Float), Column("close", Float),
    Column("pre_close", Float), Column("change", Float),
    Column("pct_chg", Numeric(15, 4)),
    Column("vol", Float), Column("amount", Float),
    # 来自 index_dailybasic
    Column("pe", Numeric(18, 4)), Column("pb", Numeric(18, 4)),
    Column("total_mv", Numeric(24, 4)), Column("float_mv", Numeric(24, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_index_daily_date", index_daily.c.trade_date)

adj_factor = Table(
    "adj_factor", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("adj_factor", Float),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_adj_factor_date", adj_factor.c.trade_date)

stk_limit = Table(   # 涨跌停"价格"（接口 stk_limit）
    "stk_limit", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("pre_close", Float),
    Column("up_limit", Float), Column("down_limit", Float),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_stk_limit_date", stk_limit.c.trade_date)

suspend = Table(   # 停复牌（接口 suspend_d）
    "suspend", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("suspend_timing", String(20)),
    Column("suspend_type", String(2)),    # S 停牌 R 复牌
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_suspend_date", suspend.c.trade_date)

stock_st = Table(   # ST 列表（接口 stock_st，3000分）
    "stock_st", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("name", String(30)),
    Column("type", String(4)),
    Column("type_name", String(30)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_stock_st_date", stock_st.c.trade_date)

# ============ 东方财富板块（6000分）============
dc_sector_daily = Table(   # 接口 dc_index
    "dc_sector_daily", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("name", String(50)),
    Column("sector_type", String(10)),    # 行业/概念/地域，按需从接口字段映射
    Column("pct_change", Numeric(15, 4)),
    Column("leading", String(30)),
    Column("leading_code", String(20)),
    Column("leading_pct", Numeric(15, 4)),
    Column("total_mv", Numeric(24, 4)),
    Column("turnover_rate", Numeric(15, 4)),
    Column("up_num", Integer), Column("down_num", Integer),
    Column("level", String(10)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_dc_sector_daily_date", dc_sector_daily.c.trade_date)

dc_sector_kline = Table(   # 接口 dc_daily
    "dc_sector_kline", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("open", Float), Column("high", Float),
    Column("low", Float), Column("close", Float),
    Column("change", Float), Column("pct_change", Numeric(15, 4)),
    Column("vol", Float), Column("amount", Float),
    Column("swing", Numeric(15, 4)), Column("turnover_rate", Numeric(15, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_dc_sector_kline_date", dc_sector_kline.c.trade_date)

dc_sector_member = Table(   # 接口 dc_member，每周快照
    "dc_sector_member", metadata,
    Column("snapshot_date", String(8), primary_key=True),
    Column("ts_code", String(20), primary_key=True),     # 板块代码
    Column("con_code", String(20), primary_key=True),    # 成分股代码
    Column("name", String(30)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_dc_member_sector", dc_sector_member.c.ts_code, dc_sector_member.c.snapshot_date)
Index("idx_dc_member_stock", dc_sector_member.c.con_code, dc_sector_member.c.snapshot_date)

# ============ 资金数据 ============
moneyflow = Table(   # 接口 moneyflow，2000分
    "moneyflow", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("buy_sm_vol", Integer), Column("buy_sm_amount", Numeric(20, 4)),
    Column("sell_sm_vol", Integer), Column("sell_sm_amount", Numeric(20, 4)),
    Column("buy_md_vol", Integer), Column("buy_md_amount", Numeric(20, 4)),
    Column("sell_md_vol", Integer), Column("sell_md_amount", Numeric(20, 4)),
    Column("buy_lg_vol", Integer), Column("buy_lg_amount", Numeric(20, 4)),
    Column("sell_lg_vol", Integer), Column("sell_lg_amount", Numeric(20, 4)),
    Column("buy_elg_vol", Integer), Column("buy_elg_amount", Numeric(20, 4)),
    Column("sell_elg_vol", Integer), Column("sell_elg_amount", Numeric(20, 4)),
    Column("net_mf_vol", Integer), Column("net_mf_amount", Numeric(20, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_moneyflow_date", moneyflow.c.trade_date)

moneyflow_hsgt = Table(   # 接口 moneyflow_hsgt
    "moneyflow_hsgt", metadata,
    Column("trade_date", String(8), primary_key=True),
    Column("ggt_ss", Numeric(20, 4)), Column("ggt_sz", Numeric(20, 4)),
    Column("hgt", Numeric(20, 4)), Column("sgt", Numeric(20, 4)),
    Column("north_money", Numeric(20, 4)), Column("south_money", Numeric(20, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)

# ============ 市场行为 ============
limit_list = Table(   # 接口 limit_list_d，涨跌停"列表"，2000分
    "limit_list", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("name", String(30)),
    Column("close", Float), Column("pct_chg", Numeric(15, 4)),
    Column("amount", Float),
    Column("limit_amount", Numeric(20, 4)),
    Column("float_mv", Numeric(24, 4)), Column("total_mv", Numeric(24, 4)),
    Column("turnover_ratio", Numeric(15, 4)),
    Column("fd_amount", Numeric(20, 4)),
    Column("first_time", String(10)), Column("last_time", String(10)),
    Column("open_times", Integer),
    Column("up_stat", String(20)),
    Column("limit_times", Integer),
    Column("limit", String(2)),     # U 涨停 D 跌停 Z 炸板
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_limit_list_date", limit_list.c.trade_date)

top_list = Table(   # 接口 top_list，2000分
    "top_list", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("name", String(30)),
    Column("close", Float), Column("pct_change", Numeric(15, 4)),
    Column("turnover_rate", Numeric(15, 4)),
    Column("amount", Float),
    Column("l_sell", Numeric(20, 4)), Column("l_buy", Numeric(20, 4)),
    Column("l_amount", Numeric(20, 4)),
    Column("net_amount", Numeric(20, 4)), Column("net_rate", Numeric(15, 4)),
    Column("amount_rate", Numeric(15, 4)),
    Column("float_values", Numeric(24, 4)),
    Column("reason", Text),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_top_list_date", top_list.c.trade_date)

top_inst = Table(   # 接口 top_inst，龙虎榜机构明细
    "top_inst", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("exalter", String(200), primary_key=True),   # 营业部名称
    Column("side", String(2)),
    Column("buy", Numeric(20, 4)), Column("buy_rate", Numeric(15, 4)),
    Column("sell", Numeric(20, 4)), Column("sell_rate", Numeric(15, 4)),
    Column("net_buy", Numeric(20, 4)),
    Column("reason", Text),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_top_inst_date", top_inst.c.trade_date)

block_trade = Table(   # 接口 block_trade，大宗交易，2000分
    "block_trade", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("trade_date", String(8), primary_key=True),
    Column("price", Float, primary_key=True),
    Column("vol", Float, primary_key=True),
    Column("amount", Numeric(20, 4)),
    Column("buyer", String(200)),
    Column("seller", String(200)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_block_trade_date", block_trade.c.trade_date)

margin_summary = Table(   # 接口 margin，融资融券汇总（按交易所）— 修复 D3
    "margin_summary", metadata,
    Column("trade_date", String(8), primary_key=True),
    Column("exchange_id", String(10), primary_key=True),   # SSE/SZSE/BSE
    Column("rzye", Numeric(24, 4)),     # 融资余额
    Column("rzmre", Numeric(24, 4)),    # 融资买入额
    Column("rqye", Numeric(24, 4)),     # 融券余额
    Column("rqmcl", Numeric(24, 4)),    # 融券卖出量
    Column("rzche", Numeric(24, 4)),    # 融资偿还额
    Column("rqyl", Numeric(24, 4)),     # 融券余量
    Column("rqchl", Numeric(24, 4)),    # 融券偿还量
    Column("rzrqye", Numeric(24, 4)),   # 融资融券余额
    Column("created_at", DateTime, server_default=func.now()),
)

# ============ 财务数据 ============
fina_indicator = Table(   # 接口 fina_indicator(_vip)，主键加 ann_date 修复 D4
    "fina_indicator", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("ann_date", String(8), primary_key=True),
    Column("end_date", String(8), primary_key=True),
    Column("update_flag", String(2)),
    # === 每股指标 ===
    Column("eps", Numeric(20, 4)), Column("dt_eps", Numeric(20, 4)),
    Column("bps", Numeric(20, 4)), Column("cfps", Numeric(20, 4)),
    Column("ocfps", Numeric(20, 4)), Column("ebit_ps", Numeric(20, 4)),
    Column("fcff_ps", Numeric(20, 4)), Column("fcfe_ps", Numeric(20, 4)),
    # === 盈利能力 ===
    Column("roe", Numeric(20, 4)), Column("roe_waa", Numeric(20, 4)),
    Column("roe_dt", Numeric(20, 4)), Column("roa", Numeric(20, 4)),
    Column("roa2", Numeric(20, 4)), Column("npta", Numeric(20, 4)),
    Column("roic", Numeric(20, 4)),
    Column("grossprofit_margin", Numeric(20, 4)),
    Column("netprofit_margin", Numeric(20, 4)),
    Column("op_income", Numeric(24, 4)), Column("ebit", Numeric(24, 4)),
    Column("ebitda", Numeric(24, 4)), Column("profit_dedt", Numeric(24, 4)),
    Column("op_to_ebt", Numeric(20, 4)), Column("nop_to_ebt", Numeric(20, 4)),
    Column("ocf_to_profit", Numeric(20, 4)), Column("ocf_to_or", Numeric(20, 4)),
    # === 成长能力 ===
    Column("or_yoy", Numeric(20, 4)), Column("op_yoy", Numeric(20, 4)),
    Column("ebt_yoy", Numeric(20, 4)), Column("netprofit_yoy", Numeric(20, 4)),
    Column("dt_netprofit_yoy", Numeric(20, 4)), Column("ocf_yoy", Numeric(20, 4)),
    Column("roe_yoy", Numeric(20, 4)), Column("bps_yoy", Numeric(20, 4)),
    Column("assets_yoy", Numeric(20, 4)), Column("eqt_yoy", Numeric(20, 4)),
    Column("tr_yoy", Numeric(20, 4)),
    # === 偿债能力 ===
    Column("current_ratio", Numeric(20, 4)), Column("quick_ratio", Numeric(20, 4)),
    Column("cash_ratio", Numeric(20, 4)), Column("debt_to_assets", Numeric(20, 4)),
    Column("debt_to_eqt", Numeric(20, 4)),
    Column("tangible_asset_to_debt", Numeric(24, 4)),
    Column("eqt_to_debt", Numeric(20, 4)),
    Column("eqt_to_interestdebt", Numeric(20, 4)),
    Column("longdebt_to_workingcapital", Numeric(20, 4)),
    # === 运营效率 ===
    Column("ar_turn", Numeric(20, 4)), Column("ca_turn", Numeric(20, 4)),
    Column("fa_turn", Numeric(20, 4)), Column("assets_turn", Numeric(20, 4)),
    Column("inv_turn", Numeric(20, 4)),
    # === 收益质量 ===
    Column("salescash_to_or", Numeric(20, 4)), Column("profit_to_op", Numeric(20, 4)),
    # === 资本结构 ===
    Column("assets_to_eqt", Numeric(20, 4)), Column("ca_to_assets", Numeric(20, 4)),
    Column("nca_to_assets", Numeric(20, 4)), Column("eqt_to_assets", Numeric(20, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_fina_indicator_end", fina_indicator.c.end_date)
Index("idx_fina_indicator_ann", fina_indicator.c.ann_date)

forecast = Table(   # 接口 forecast，业绩预告
    "forecast", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("ann_date", String(8), primary_key=True),
    Column("end_date", String(8), primary_key=True),
    Column("type", String(20)),
    Column("p_change_min", Numeric(20, 4)), Column("p_change_max", Numeric(20, 4)),
    Column("net_profit_min", Numeric(24, 4)), Column("net_profit_max", Numeric(24, 4)),
    Column("last_parent_net", Numeric(24, 4)),
    Column("summary", Text), Column("change_reason", Text),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_forecast_ann", forecast.c.ann_date)

express = Table(   # 接口 express，业绩快报
    "express", metadata,
    Column("ts_code", String(20), primary_key=True),
    Column("ann_date", String(8), primary_key=True),
    Column("end_date", String(8), primary_key=True),
    Column("revenue", Numeric(24, 4)), Column("operate_profit", Numeric(24, 4)),
    Column("total_profit", Numeric(24, 4)), Column("n_income", Numeric(24, 4)),
    Column("total_assets", Numeric(24, 4)),
    Column("yoy_sales", Numeric(20, 4)), Column("yoy_net_profit", Numeric(20, 4)),
    Column("diluted_roe", Numeric(20, 4)),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("idx_express_ann", express.c.ann_date)

# ============ 系统表 ============
task_failure_log = Table(
    "task_failure_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("collector", String(40)),
    Column("trade_date", String(8)),
    Column("ts_code", String(20)),
    Column("error_type", String(30)),
    Column("error_message", Text),
    Column("context", Text),               # JSON 字符串
    Column("retry_count", Integer, server_default="0"),
    Column("status", String(12), server_default="pending"),  # pending/resolved
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now()),
    Column("resolved_at", DateTime),
)
Index("idx_failure_status", task_failure_log.c.status)
Index("idx_failure_collector", task_failure_log.c.collector, task_failure_log.c.status)

# ============ 注册表 ============
TABLES = {t.name: t for t in metadata.tables.values()}
