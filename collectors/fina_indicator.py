# -*- coding: utf-8 -*-
"""财务指标采集器（接口 fina_indicator_vip，5000 分）。

按报告期(period)批量取全市场财务指标。主键 (ts_code, ann_date, end_date)，
保留财报重述记录（修复 D4）。CORE_FIELDS 必须是 schema fina_indicator 列的子集。
"""
from config.settings import settings
from collectors.base_collector import PeriodBasedCollector
import pandas as pd

# 与 models/schema.py 的 fina_indicator 列对齐（除 created_at）
CORE_FIELDS = [
    "ts_code", "ann_date", "end_date", "update_flag",
    # 每股指标
    "eps", "dt_eps", "bps", "cfps", "ocfps", "ebit_ps", "fcff_ps", "fcfe_ps",
    # 盈利能力
    "roe", "roe_waa", "roe_dt", "roa", "roa2", "npta", "roic",
    "grossprofit_margin", "netprofit_margin", "op_income", "ebit", "ebitda",
    "profit_dedt", "op_to_ebt", "nop_to_ebt", "ocf_to_profit", "ocf_to_or",
    # 成长能力
    "or_yoy", "op_yoy", "ebt_yoy", "netprofit_yoy", "dt_netprofit_yoy",
    "ocf_yoy", "roe_yoy", "bps_yoy", "assets_yoy", "eqt_yoy", "tr_yoy",
    # 偿债能力
    "current_ratio", "quick_ratio", "cash_ratio", "debt_to_assets",
    "debt_to_eqt", "tangible_asset_to_debt", "eqt_to_debt",
    "eqt_to_interestdebt", "longdebt_to_workingcapital",
    # 运营效率
    "ar_turn", "ca_turn", "fa_turn", "assets_turn", "inv_turn",
    # 收益质量
    "salescash_to_or", "profit_to_op",
    # 资本结构
    "assets_to_eqt", "ca_to_assets", "nca_to_assets", "eqt_to_assets",
]


class FinaIndicatorCollector(PeriodBasedCollector):
    """全市场财务指标，按报告期采集。"""

    TASK_NAME = "fina_indicator"
    TABLE_NAME = settings.TBL_FINA_INDICATOR
    KEY_FIELDS = ["ts_code", "ann_date", "end_date"]
    REQUIRED_POINTS = 5000

    _FIELDS = ",".join(CORE_FIELDS)

    def fetch_by_period(self, period: str) -> pd.DataFrame:
        return self.client.query("fina_indicator_vip", period=period, fields=self._FIELDS)
